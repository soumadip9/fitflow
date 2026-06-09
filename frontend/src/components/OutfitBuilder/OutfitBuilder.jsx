import { useState, useEffect, useCallback } from 'react';
import { useWardrobe } from '../../context/WardrobeContext';
import { useAuth } from '../../context/AuthContext';
import { useClothingTransparentUrls } from '../../hooks/useClothingTransparentUrls';
import { OutfitCompositeStack } from './OutfitCompositeStack';
import { fetchWithTimeout } from '../../utils/fetchWithTimeout';
import { API_BASE } from '../../config';
import './OutfitBuilder.css';

const occasionOptions = [
    { value: 'casual_day', label: 'Casual Day' },
    { value: 'office', label: 'Office' },
    { value: 'party', label: 'Party' },
    { value: 'date_night', label: 'Date Night' },
    { value: 'gym', label: 'Gym' },
    { value: 'travel', label: 'Travel' },
    { value: 'formal_event', label: 'Formal Event' },
];

const upperwearClasses = new Set([
    'blazer', 'cardigan', 'casual', 'dress', 'formal_shirt', 'hoodie', 'longsleeve',
    'pullover', 'sweaters', 'sweatshirt', 't-shirt', 'top', 'vest'
]);
const lowerwearClasses = new Set(['jeans', 'shorts', 'skirt', 'trousers']);
const shoeClasses = new Set(['boot', 'heel', 'slide', 'sneaker', 'sport']);
const accessoryClasses = new Set(['watch', 'belt', 'cap', 'bag', 'sunglasses']);

const getBuilderCategory = (itemCategory) => {
    const category = (itemCategory || '').toLowerCase().trim();
    if (upperwearClasses.has(category)) return 'Upperwear';
    if (lowerwearClasses.has(category)) return 'Lowerwear';
    if (shoeClasses.has(category)) return 'Shoes';
    if (accessoryClasses.has(category)) return 'Accessories';
    return 'Accessories';
};

const getBuilderCategoryFromItem = (item) => {
    const byCategory = getBuilderCategory(item?.category);
    if (byCategory !== 'Accessories') return byCategory;

    const name = String(item?.name || item?.display_name || '').toLowerCase();
    if ([...lowerwearClasses].some(cls => name.includes(cls))) return 'Lowerwear';
    if ([...shoeClasses].some(cls => name.includes(cls))) return 'Shoes';
    if ([...upperwearClasses].some(cls => name.includes(cls))) return 'Upperwear';
    if ([...accessoryClasses].some(cls => name.includes(cls))) return 'Accessories';
    return 'Accessories';
};

/** Map wardrobe item → layer key (top / bottom only). */
const slotKeyFromItem = (item) => {
    const g = getBuilderCategoryFromItem(item);
    if (g === 'Upperwear') return 'top';
    if (g === 'Lowerwear') return 'bottom';
    if (g === 'Shoes') return 'shoes';
    return null;
};

const SIDEBAR_GROUPS = [
    { key: 'Upperwear', label: 'Top' },
    { key: 'Lowerwear', label: 'Bottom' },
];

/** Backend expects display_name; wardrobe UI uses name. */
const slotForRateApi = (item) => {
    if (!item) return null;
    return {
        ...item,
        display_name: item.display_name ?? item.name,
    };
};

const SparklesIcon = () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2l2.4 7.2H22l-6 4.8 2.4 7.2L12 16.4l-6.4 4.8L8 14l-6-4.8h7.6z" />
    </svg>
);
const HeartIcon = () => (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="#f7b1ab" stroke="#f7b1ab" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z" />
    </svg>
);

function OutfitBuilder() {
    const { wardrobeItems, saveOutfit, loadingWardrobe } = useWardrobe();
    /**
     * Visual outfit state: image URL per slot (required) + full item for API/save.
     * Shape per slot: { image: string, item: object } | null
     */
    const [layers, setLayers] = useState({
        top: null,
        bottom: null,
        shoes: null,
    });
    const [modelDragOver, setModelDragOver] = useState(false);

    const [outfitName, setOutfitName] = useState('');
    /** Wardrobe items chosen by AI (cards: top, bottom, footwear) */
    const [aiPicks, setAiPicks] = useState({
        top: null,
        bottom: null,
        shoes: null,
        accessory: null,
    });
    /** Up to 2 strict combos from /build-outfit, ordered by occasion preview rating */
    const [rankedOptions, setRankedOptions] = useState([]);
    const [activeComboIndex, setActiveComboIndex] = useState(0);
    /** @type {'ai' | 'manual'} */
    const [activeSection, setActiveSection] = useState('manual');
    const [occasion, setOccasion] = useState('party');
    const [saved, setSaved] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [isRating, setIsRating] = useState(false);
    const [feedback, setFeedback] = useState(null);
    const [feedbackError, setFeedbackError] = useState('');
    /** Shown when the API used a relaxed / closest wardrobe match */
    const [buildNotice, setBuildNotice] = useState('');
    const { token, user } = useAuth();
    const { display: layerDisplayUrls, processing: bgProcessing, removalEnabled, cutoutMeta } =
        useClothingTransparentUrls(layers, token);

    const [profileGender, setProfileGender] = useState('');

    useEffect(() => {
        const fetchGender = async () => {
            if (!token) return;
            try {
                const response = await fetchWithTimeout(`${API_BASE}/profile`, {
                    headers: { Authorization: `Bearer ${token}` }
                });
                if (response.ok) {
                    const data = await response.json();
                    setProfileGender(data?.gender || '');
                }
            } catch (err) {
                console.error("Error fetching profile", err);
            }
        };
        fetchGender();
    }, [token]);

    const getProfileGender = useCallback(() => {
        return profileGender;
    }, [profileGender]);

    useEffect(() => {
        setRankedOptions([]);
        setActiveComboIndex(0);
    }, [occasion]);

    const availableItems = wardrobeItems.filter(i => i.status === 'available');

    const findWardrobeMatch = (aiItem) => {
        if (!aiItem) return null;
        const id = String(aiItem._id ?? aiItem.id ?? '');
        if (id) {
            const byId = availableItems.find(i => String(i.id) === id);
            if (byId) return byId;
        }
        const targetGroup = getBuilderCategory(aiItem.category);
        const matches = availableItems.filter(
            i => getBuilderCategoryFromItem(i) === targetGroup
        );
        const byColor = matches.find(i => i.color === aiItem.color);
        if (byColor) return byColor;
        if (matches[0]) return matches[0];
        // Backend picked valid Mongo items — show them even if local wardrobe cache is stale.
        if (aiItem.image || aiItem.display_name || aiItem.category) {
            return {
                id: id || `api-${aiItem.category}-${aiItem.color}`,
                name: aiItem.display_name || aiItem.name || aiItem.category,
                display_name: aiItem.display_name || aiItem.name || aiItem.category,
                category: aiItem.category,
                color: aiItem.color,
                image: aiItem.image,
                status: 'available',
            };
        }
        return null;
    };

    const findAccessoryWardrobeMatch = (aiItem) => {
        if (!aiItem) return null;
        const id = String(aiItem._id ?? aiItem.id ?? '');
        if (id) {
            const byId = availableItems.find(i => String(i.id) === id);
            if (byId) return byId;
        }
        const cat = (aiItem.category || '').toLowerCase();
        return (
            availableItems.find(i => (i.category || '').toLowerCase() === cat) || null
        );
    };

    const assignToSlot = (item) => {
        const slot = slotKeyFromItem(item);
        if (!slot) return;
        setLayers((prev) => ({
            ...prev,
            [slot]: { image: item.image, item: { ...item } },
        }));
    };

    const handleDragStart = (e, item) => {
        e.dataTransfer.effectAllowed = 'copy';
        e.dataTransfer.setData(
            'application/json',
            JSON.stringify({
                id: item.id,
                image: item.image,
                category: item.category,
            })
        );
        try {
            if (e.dataTransfer.setDragImage && e.currentTarget) {
                e.dataTransfer.setDragImage(e.currentTarget, 36, 36);
            }
        } catch {
            /* ignore */
        }
    };

    const handleModelDragOver = (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
        setModelDragOver(true);
    };

    const handleModelDragLeave = (e) => {
        if (!e.currentTarget.contains(e.relatedTarget)) {
            setModelDragOver(false);
        }
    };

    const handleModelDrop = (e) => {
        e.preventDefault();
        setModelDragOver(false);
        const raw = e.dataTransfer.getData('application/json');
        if (!raw) return;
        try {
            const data = JSON.parse(raw);
            const item = availableItems.find((i) => String(i.id) === String(data.id));
            if (!item) return;
            assignToSlot(item);
        } catch {
            /* ignore */
        }
    };

    const handleSaveOutfit = () => {
        const items = [layers.top?.item, layers.bottom?.item, layers.shoes?.item].filter(Boolean);
        if (items.length === 0) return;
        saveOutfit({
            name: outfitName || `Outfit ${Date.now().toString(36)}`,
            items,
        });
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
        setLayers({ top: null, bottom: null, shoes: null });
        setOutfitName('');
    };

    const BUILD_OUTFIT_MS = 45000;
    const RATE_OUTFIT_MS = 60000;

    const handleGenerateSuggestion = async () => {
        if (loadingWardrobe) {
            setFeedbackError('Wardrobe is still loading — please wait a moment and try again.');
            return;
        }
        setIsGenerating(true);
        setFeedback(null);
        setFeedbackError('');
        setBuildNotice('');
        setRankedOptions([]);
        setActiveComboIndex(0);
        setAiPicks({ top: null, bottom: null, shoes: null, accessory: null });
        setLayers({ top: null, bottom: null });
        try {
            const profileGender = getProfileGender();
            const res = await fetchWithTimeout(
                `${API_BASE}/build-outfit`,
                {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        occasion,
                        ...(profileGender ? { gender: profileGender } : {}),
                    }),
                },
                BUILD_OUTFIT_MS
            );
            if (res.ok) {
                const data = await res.json();
                if (Array.isArray(data.warnings) && data.warnings.length > 0) {
                    setBuildNotice(data.warnings.join(' '));
                }
                if (data.message) {
                    setBuildNotice(data.message);
                }
                if (data.outfit) {
                    const ranked = Array.isArray(data.ranked_options)
                        ? data.ranked_options
                        : [];
                    if (ranked.length > 0) {
                        setRankedOptions(ranked);
                        setActiveComboIndex(0);
                    }
                    const primary =
                        ranked.length > 0 ? ranked[0].outfit : data.outfit;

                    const topMatch = findWardrobeMatch(primary.top);
                    const bottomMatch = findWardrobeMatch(primary.bottom);
                    const shoesMatch = findWardrobeMatch(primary.shoes);
                    const accessoryMatch = findAccessoryWardrobeMatch(primary.accessory);

                    if (topMatch || bottomMatch || shoesMatch) {
                        await handleRateOutfitFromLayers({
                            top: topMatch,
                            bottom: bottomMatch,
                            shoes: shoesMatch,
                            accessory: accessoryMatch,
                        });
                        setAiPicks({
                            top: topMatch,
                            bottom: bottomMatch,
                            shoes: shoesMatch,
                            accessory: accessoryMatch,
                        });
                        setLayers({
                            top: topMatch ? { image: topMatch.image, item: { ...topMatch } } : null,
                            bottom: bottomMatch
                                ? { image: bottomMatch.image, item: { ...bottomMatch } }
                                : null,
                            shoes: shoesMatch ? { image: shoesMatch.image, item: { ...shoesMatch } } : null,
                        });
                        setIsGenerating(false);
                        return;
                    } else {
                        setBuildNotice('No items in your wardrobe match the suggested style.');
                    }
                }
                setFeedbackError(data.message || 'Could not build outfit for selected occasion.');
                await handleRateOutfitFromLayers();
                setIsGenerating(false);
                return;
            }
        } catch (err) {
            console.error('Suggestion failed', err);
            const aborted = err?.name === 'AbortError';
            setFeedbackError(
                aborted
                    ? 'Suggestion timed out — the backend may be waking up. Wait 30 seconds and try again.'
                    : 'Could not generate outfit. Check that the backend is running and try again.'
            );
        }

        setIsGenerating(false);
    };

    const handleRateOutfitFromLayers = async (built = null) => {
        const top = built?.top ?? layers.top?.item ?? null;
        const bottom = built?.bottom ?? layers.bottom?.item ?? null;
        const shoes =
            built != null && Object.prototype.hasOwnProperty.call(built, 'shoes')
                ? built.shoes
                : aiPicks.shoes;
        const accessory =
            built != null && Object.prototype.hasOwnProperty.call(built, 'accessory')
                ? built.accessory
                : aiPicks.accessory ?? null;

        const outfitPayload = {
            top: slotForRateApi(top),
            bottom: slotForRateApi(bottom),
            shoes: slotForRateApi(shoes),
            accessory: slotForRateApi(accessory),
            outerwear: null,
        };

        setIsRating(true);
        setFeedbackError('');

        const profileGender = getProfileGender();
        const requestBody = JSON.stringify({
            occasion,
            outfit: outfitPayload,
            ...(profileGender ? { gender: profileGender } : {}),
        });

        const attemptRate = async () => {
            const res = await fetchWithTimeout(
                `${API_BASE}/rate-outfit`,
                {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json',
                    },
                    body: requestBody,
                },
                RATE_OUTFIT_MS
            );
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Failed to rate outfit');
            return data;
        };

        try {
            let data;
            try {
                data = await attemptRate();
            } catch (firstErr) {
                // One automatic retry for transient network/timeout blips before surfacing an error.
                console.warn('Rate outfit attempt failed, retrying once', firstErr);
                data = await attemptRate();
            }
            setFeedback(data);
        } catch (err) {
            console.error('Failed to rate outfit', err);
            setFeedbackError(
                err?.name === 'AbortError'
                    ? 'Feedback is taking longer than usual — please try again in a moment.'
                    : 'Could not fetch feedback right now. Please try again.'
            );
        } finally {
            setIsRating(false);
        }
    };

    const handleComboSelect = async (index) => {
        const row = rankedOptions[index];
        if (!row?.outfit) return;
        setActiveComboIndex(index);
        const o = row.outfit;
        const topMatch = findWardrobeMatch(o.top);
        const bottomMatch = findWardrobeMatch(o.bottom);
        const shoesMatch = findWardrobeMatch(o.shoes);
        const accessoryMatch = findAccessoryWardrobeMatch(o.accessory);
        if (!topMatch && !bottomMatch && !shoesMatch) {
            setBuildNotice('Could not display this match — try “Suggest outfit” again.');
            return;
        }
        setAiPicks({ top: null, bottom: null, shoes: null, accessory: null });
        setLayers({ top: null, bottom: null });
        await handleRateOutfitFromLayers({
            top: topMatch,
            bottom: bottomMatch,
            shoes: shoesMatch,
            accessory: accessoryMatch,
        });
        setAiPicks({
            top: topMatch,
            bottom: bottomMatch,
            shoes: shoesMatch,
            accessory: accessoryMatch,
        });
        setLayers({
            top: topMatch ? { image: topMatch.image, item: { ...topMatch } } : null,
            bottom: bottomMatch ? { image: bottomMatch.image, item: { ...bottomMatch } } : null,
            shoes: shoesMatch ? { image: shoesMatch.image, item: { ...shoesMatch } } : null,
        });
    };

    const handleNextMatch = async () => {
        if (rankedOptions.length < 2) return;
        const next = (activeComboIndex + 1) % rankedOptions.length;
        await handleComboSelect(next);
    };

    const handleRateOutfit = () => handleRateOutfitFromLayers();

    const filledSlots = [layers.top, layers.bottom, layers.shoes].filter(Boolean).length;

    const outfitModel = (interactive) => (
        <div
            className={`model ${interactive && modelDragOver ? 'model--drag-over' : ''}`}
            onDragOver={interactive ? handleModelDragOver : undefined}
            onDragLeave={interactive ? handleModelDragLeave : undefined}
            onDrop={interactive ? handleModelDrop : undefined}
        >
            <div className="model__stage" aria-hidden="true">
                <div className="model__stage-bg" />
                <div className="model__stage-shine" />
                <div className="model__stage-grid" />
            </div>
            {!layerDisplayUrls.top && !layerDisplayUrls.bottom && (
                <p className="model__empty-hint">
                    {interactive ? 'Drop tops & bottoms here' : 'Your look will appear here'}
                </p>
            )}
            <OutfitCompositeStack
                topUrl={layerDisplayUrls.top || undefined}
                bottomUrl={layerDisplayUrls.bottom || undefined}
                topCutoutClass={
                    removalEnabled === true && cutoutMeta.top?.backgroundRemoved
                        ? 'layer-img--cutout'
                        : ''
                }
                bottomCutoutClass={
                    removalEnabled === true && cutoutMeta.bottom?.backgroundRemoved
                        ? 'layer-img--cutout'
                        : ''
                }
                titleTop={
                    removalEnabled &&
                    cutoutMeta.top &&
                    !cutoutMeta.top.backgroundRemoved
                        ? 'Showing original photo — background could not be removed (checkered preview unavailable)'
                        : ''
                }
                titleBottom={
                    removalEnabled &&
                    cutoutMeta.bottom &&
                    !cutoutMeta.bottom.backgroundRemoved
                        ? 'Showing original photo — background could not be removed (checkered preview unavailable)'
                        : ''
                }
            />
        </div>
    );
    return (
        <div className="outfit-builder">
            <div className="panel-header">
                <h1 className="panel-header__title">Outfit Builder</h1>
                <p className="panel-header__subtitle">
                    {activeSection === 'ai'
                        ? 'Pick an occasion and get AI-matched pieces and feedback.'
                        : 'Drag tops and bottoms into the preview, name your outfit, and save to Favourites.'}
                </p>
            </div>

            <div className="outfit-builder__section-tabs" role="tablist" aria-label="Builder mode">
                <button
                    type="button"
                    role="tab"
                    id="tab-ai"
                    aria-selected={activeSection === 'ai'}
                    aria-controls="panel-ai"
                    className={`outfit-builder__section-tab ${activeSection === 'ai' ? 'outfit-builder__section-tab--active' : ''}`}
                    onClick={() => setActiveSection('ai')}
                >
                    AI suggestions
                </button>
                <button
                    type="button"
                    role="tab"
                    id="tab-manual"
                    aria-selected={activeSection === 'manual'}
                    aria-controls="panel-manual"
                    className={`outfit-builder__section-tab ${activeSection === 'manual' ? 'outfit-builder__section-tab--active' : ''}`}
                    onClick={() => setActiveSection('manual')}
                >
                    Manual builder
                </button>
            </div>

            {activeSection === 'ai' && (
                <div
                    id="panel-ai"
                    role="tabpanel"
                    aria-labelledby="tab-ai"
                    className="outfit-builder__panel outfit-builder__panel--ai"
                >
                    <div className="card occasion-card occasion-card--in-ai">
                        <label className="label" htmlFor="occasion-select">Occasion</label>
                        <select
                            id="occasion-select"
                            className="select"
                            value={occasion}
                            onChange={(e) => setOccasion(e.target.value)}
                        >
                            {occasionOptions.map(opt => (
                                <option key={opt.value} value={opt.value}>{opt.label}</option>
                            ))}
                        </select>
                    </div>

                    <div className="card outfit-builder__ai-intro">
                        <h2 className="outfit-builder__panel-title">Suggested outfit</h2>
                        <p className="outfit-builder__ai-copy">
                            Pick an occasion, then get three cards — top, bottom, and footwear — from your wardrobe.
                            We score the full look. Use <strong>Manual builder</strong> to drag pieces yourself.
                        </p>
                        <button
                            type="button"
                            className="btn btn--primary outfit-builder__ai-suggest"
                            onClick={handleGenerateSuggestion}
                            id="generate-suggestion-btn"
                            disabled={isGenerating}
                        >
                            <SparklesIcon /> {isGenerating ? 'Generating…' : 'Suggest outfit'}
                        </button>

                        {rankedOptions.length > 1 && (
                            <div
                                className="outfit-combo-nav"
                                role="group"
                                aria-label="Step through ranked outfit matches"
                            >
                                <p className="outfit-combo-nav__meta">
                                    Match {activeComboIndex + 1} of {rankedOptions.length}
                                    {isRating && <span style={{ marginLeft: 8, opacity: 0.5, fontSize: '0.8em' }}>rating…</span>}
                                    {!isRating && feedback?.rating != null && (
                                        <> · <strong style={{ color: feedback.rating >= 8 ? '#22c55e' : feedback.rating >= 6 ? '#f59e0b' : '#ef4444' }}>{feedback.rating}/10</strong> ✨</>
                                    )}
                                </p>
                                <button
                                    type="button"
                                    className="btn btn--secondary outfit-combo-nav__next"
                                    onClick={handleNextMatch}
                                    disabled={isGenerating || isRating}
                                >
                                    Next match
                                </button>
                            </div>
                        )}

                        <div className="ai-suggestion-cards" aria-label="Selected outfit pieces">
                            {[
                                { key: 'top', label: 'Top' },
                                { key: 'bottom', label: 'Bottom' },
                                { key: 'shoes', label: 'Footwear' },
                            ].map(({ key, label }) => {
                                const item = layers[key]?.item || aiPicks[key];
                                const name = item?.name || item?.display_name;
                                return (
                                    <article key={key} className="ai-suggestion-card">
                                        <div className="ai-suggestion-card__label">{label}</div>
                                        <div className="ai-suggestion-card__media">
                                            {item?.image ? (
                                                <img src={item.image} alt="" className="ai-suggestion-card__img" />
                                            ) : (
                                                <div className="ai-suggestion-card__placeholder">
                                                    {isGenerating ? '…' : (buildNotice ? 'No appropriate item' : '—')}
                                                </div>
                                            )}
                                        </div>
                                        <div className="ai-suggestion-card__name" title={name || ''}>
                                            {name || (isGenerating ? 'Searching…' : (buildNotice ? 'No appropriate outfit found' : 'Empty'))}
                                        </div>
                                    </article>
                                );
                            })}
                        </div>
                    </div>

                    <section className="model-canvas card outfit-builder__ai-preview" aria-label="Suggested look preview">
                        <div className="model-canvas__header">
                            <span className="model-canvas__title">Preview</span>
                            <button
                                type="button"
                                className="btn btn--secondary model-canvas__go-manual"
                                onClick={() => setActiveSection('manual')}
                            >
                                Edit manually
                            </button>
                        </div>
                        {outfitModel(false)}
                        <p className="model-canvas__hint">
                            {filledSlots === 0
                                ? 'Run “Suggest outfit” to fill this preview.'
                                : 'Preview only — open Manual builder to change pieces.'}
                        </p>
                        {buildNotice ? (
                            <p className="model-canvas__build-notice" role="status">
                                {buildNotice}
                            </p>
                        ) : null}
                    </section>

                    <div className="outfit-name-input outfit-name-input--in-ai">
                        <label className="label" htmlFor="outfit-name-ai">Outfit Name</label>
                        <input
                            id="outfit-name-ai"
                            className="input"
                            placeholder="Give your outfit a name..."
                            value={outfitName}
                            onChange={(e) => setOutfitName(e.target.value)}
                            style={{ maxWidth: 360 }}
                        />
                    </div>

                    <div className="outfit-actions outfit-actions--ai">
                        <button
                            type="button"
                            className="btn btn--secondary"
                            onClick={() => handleRateOutfit()}
                            disabled={isRating || filledSlots === 0}
                        >
                            {isRating ? 'Rating…' : 'Get Feedback'}
                        </button>
                        <button
                            type="button"
                            className="btn btn--primary"
                            onClick={handleSaveOutfit}
                            disabled={filledSlots === 0}
                            id="save-outfit-btn-ai"
                        >
                            <HeartIcon /> Save to Favourites
                        </button>
                    </div>

                    {(feedback || feedbackError) && (
                        <div className="card feedback-card">
                            <div className="feedback-card__title">Outfit feedback</div>
                            {feedbackError && <div className="feedback-card__error">{feedbackError}</div>}
                            {feedback && (
                                <>
                                    {/* ── Big Score Ring ── */}
                                    <div className="feedback-score-hero">
                                        <div className="feedback-score-ring" style={{
                                            '--score-pct': `${(feedback.rating / 10) * 100}%`,
                                            '--ring-color': feedback.rating >= 8
                                                ? '#22c55e'
                                                : feedback.rating >= 6
                                                ? '#f59e0b'
                                                : '#ef4444',
                                        }}>
                                            <svg viewBox="0 0 80 80" className="feedback-score-svg">
                                                <circle cx="40" cy="40" r="34" className="feedback-score-track" />
                                                <circle cx="40" cy="40" r="34" className="feedback-score-fill"
                                                    style={{
                                                        strokeDasharray: `${(feedback.rating / 10) * 213.6} 213.6`,
                                                        stroke: feedback.rating >= 8 ? '#22c55e' : feedback.rating >= 6 ? '#f59e0b' : '#ef4444',
                                                    }}
                                                />
                                            </svg>
                                            <div className="feedback-score-center">
                                                <span className="feedback-score-number">{feedback.rating}</span>
                                                <span className="feedback-score-denom">/10</span>
                                            </div>
                                        </div>
                                        <div className="feedback-score-meta">
                                            <div className="feedback-score-label">
                                                {feedback.rating >= 8 ? 'Great look' : feedback.rating >= 6 ? 'Solid fit' : 'Needs work'}
                                            </div>
                                            <span className="feedback-score-occasion">
                                                {(occasion || 'casual day').replace(/_/g, ' ')}
                                            </span>
                                        </div>
                                    </div>

                                    <div className="feedback-card__text">{feedback.feedback}</div>

                                    {feedback.why_it_works && (
                                        <div className="feedback-card__why">
                                            <strong
                                                style={{
                                                    color: feedback.rating >= 7
                                                        ? '#22c55e'
                                                        : feedback.rating >= 5
                                                            ? '#f59e0b'
                                                            : '#ef4444',
                                                }}
                                            >
                                                {feedback.rating >= 7
                                                    ? 'Why This Works'
                                                    : feedback.rating >= 5
                                                        ? 'The Verdict'
                                                        : "What's Holding It Back"}
                                            </strong>
                                            <p>{feedback.why_it_works}</p>
                                        </div>
                                    )}

                                    {feedback.issues?.length > 0 && (
                                        <div className="feedback-card__block">
                                            <strong>Issues</strong>
                                            <ul className="feedback-list feedback-list--issues">
                                                {feedback.issues.map((issue, i) => <li key={i}>{issue}</li>)}
                                            </ul>
                                        </div>
                                    )}
                                    {feedback.suggestions?.length > 0 && (
                                        <div className="feedback-card__block">
                                            <strong>Suggestions</strong>
                                            <ul className="feedback-list feedback-list--suggestions">
                                                {feedback.suggestions.map((s, i) => <li key={i}>{s}</li>)}
                                            </ul>
                                        </div>
                                    )}
                                    
                                    {feedback.shopping_products?.length > 0 && (
                                        <div className="feedback-card__shopping">
                                            <h3 className="shopping-title">Shopping Suggestions</h3>
                                            <p className="shopping-subtitle">Fill the gaps in your outfit</p>
                                            <div className="shopping-groups-container">
                                                {feedback.shopping_products.map((group, idx) => (
                                                    <div key={idx} className="shopping-group">
                                                        <h4 className="shopping-group-title">{group.query}</h4>
                                                        <div className="shopping-products-grid">
                                                            {group.products.map((p, i) => (
                                                                <a key={i} href={p.link} target="_blank" rel="noopener noreferrer" className="shopping-product-card" title={p.title}>
                                                                    <div className={`shopping-product-img-wrapper ${!p.image ? 'shopping-product-img-wrapper--empty' : ''}`}>
                                                                        {p.image ? (
                                                                            <img src={p.image} alt="" className="shopping-product-img" loading="lazy" />
                                                                        ) : (
                                                                            <div className="shopping-product-placeholder">No Preview</div>
                                                                        )}
                                                                    </div>
                                                                    <div className="shopping-product-details">
                                                                        <div className="shopping-product-title">{p.title}</div>
                                                                        <div className="shopping-product-price">{p.price || 'View Price'}</div>
                                                                        <div className="shopping-product-buy">Buy Now</div>
                                                                    </div>
                                                                </a>
                                                            ))}
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </>
                            )}
                        </div>
                    )}
                </div>
            )}

            {activeSection === 'manual' && (
                <div
                    id="panel-manual"
                    role="tabpanel"
                    aria-labelledby="tab-manual"
                    className="outfit-builder__panel outfit-builder__panel--manual"
                >
                    <div className="outfit-builder__workspace">
                        <aside className="wardrobe-sidebar card" aria-label="Wardrobe by category">
                            {SIDEBAR_GROUPS.map(({ key, label }) => {
                                const items = availableItems.filter(i => getBuilderCategoryFromItem(i) === key);
                                return (
                                    <div key={key} className="wardrobe-sidebar__group">
                                        <div className="wardrobe-sidebar__label">{label}</div>
                                        {items.length === 0 ? (
                                            <div className="wardrobe-sidebar__empty">No items</div>
                                        ) : (
                                            <div className="wardrobe-sidebar__items">
                                                {items.map(item => (
                                                    <button
                                                        key={item.id}
                                                        type="button"
                                                        className="wardrobe-thumb"
                                                        draggable
                                                        onDragStart={(e) => handleDragStart(e, item)}
                                                        title={`${item.name || item.display_name || 'Item'} — drag into preview`}
                                                    >
                                                        <img
                                                            src={item.image}
                                                            alt=""
                                                            className="wardrobe-thumb__img"
                                                            loading="lazy"
                                                            draggable={false}
                                                        />
                                                    </button>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </aside>

                        <section className="model-canvas card" aria-label="Outfit preview">
                            <div className="model-canvas__header">
                                <span className="model-canvas__title">Your look</span>
                                <button
                                    type="button"
                                    className="model-canvas__reset"
                                    onClick={() => {
                                        setLayers({ top: null, bottom: null, shoes: null });
                                        setAiPicks({
                                            top: null,
                                            bottom: null,
                                            shoes: null,
                                            accessory: null,
                                        });
                                    }}
                                    disabled={filledSlots === 0}
                                >
                                    Clear all
                                </button>
                            </div>

                            {outfitModel(true)}

                            <div className="outfit-builder-cards-manual">
                                {[
                                    { key: 'top', label: 'Top' },
                                    { key: 'bottom', label: 'Bottom' },
                                ].map(({ key, label }) => {
                                    const item = layers[key]?.item;
                                    const name = item?.name || item?.display_name;
                                    return (
                                        <div key={key} className="manual-item-status">
                                            <span className="manual-item-status__dot" style={{ backgroundColor: item ? '#22c55e' : '#64748b' }}></span>
                                            <span className="manual-item-status__label">{label}:</span>
                                            <span className="manual-item-status__name">{name || 'Empty'}</span>
                                        </div>
                                    );
                                })}
                            </div>
                        </section>
                    </div>

                    <div className="card outfit-builder__manual-save">
                        <label className="label" htmlFor="outfit-name-manual">Outfit Name</label>
                        <input
                            id="outfit-name-manual"
                            className="input outfit-builder__manual-name-input"
                            placeholder="Give your outfit a name..."
                            value={outfitName}
                            onChange={(e) => setOutfitName(e.target.value)}
                        />
                        <button
                            type="button"
                            className="btn btn--primary outfit-builder__manual-save-btn"
                            onClick={handleSaveOutfit}
                            disabled={filledSlots === 0}
                            id="save-outfit-btn"
                        >
                            <HeartIcon /> Save to Favourites
                        </button>
                    </div>
                </div>
            )}

            {saved && (
                <div className="save-toast">✓ Outfit saved to Favourites</div>
            )}
        </div>
    );
}

export default OutfitBuilder;
