import { useEffect, useMemo, useRef, useState } from 'react';
import { styleOptions, colorOptions } from '../../data/mockData';
import { useAuth } from '../../context/AuthContext';
import { useWardrobe } from '../../context/WardrobeContext';
import axios from 'axios';
import { API_BASE } from '../../config';
import './Profile.css';

function Profile() {
    const { user, updateUserName, updateUserAvatar } = useAuth();
    const { wardrobeItems } = useWardrobe();
    const displayName = user?.name || 'User';
    const fileInputRef = useRef(null);
    const [profile, setProfile] = useState({
        gender: '',
        age: '',
        styles: [],
        colors: [],
    });
    const [saved, setSaved] = useState(false);
    const [editedName, setEditedName] = useState(displayName);
    const [dpError, setDpError] = useState('');
    const favoriteColorsSummary = profile.colors.length > 0 ? profile.colors.slice(0, 3).join(', ') : 'Not set';

    const [isEditing, setIsEditing] = useState(false);

    useEffect(() => {
        const fetchProfile = async () => {
            const token = localStorage.getItem('token');
            if (!token) return;
            try {
                const response = await axios.get(`${API_BASE}/profile`, {
                    headers: { Authorization: `Bearer ${token}` }
                });
                const parsed = response.data;
                setProfile({
                    gender: parsed?.gender || '',
                    age: parsed?.age ?? '',
                    styles: Array.isArray(parsed?.fashion_styles) ? parsed.fashion_styles : [],
                    colors: Array.isArray(parsed?.preferred_colors) ? parsed.preferred_colors : [],
                });
                if (parsed?.display_name && parsed.display_name !== displayName) {
                    updateUserName(parsed.display_name);
                }
                if (parsed?.profile_image && !user?.avatar) {
                    updateUserAvatar(parsed.profile_image);
                }
            } catch (error) {
                console.error("Error fetching profile from backend", error);
            }
        };
        fetchProfile();
    }, [user?.email]);

    useEffect(() => {
        setEditedName(displayName);
    }, [displayName]);

    const handleGenderChange = (e) => {
        setProfile(prev => ({ ...prev, gender: e.target.value }));
    };

    const handleAgeChange = (e) => {
        setProfile(prev => ({ ...prev, age: e.target.value }));
    };

    const toggleStyle = (style) => {
        if (!isEditing) return;
        setProfile(prev => ({
            ...prev,
            styles: prev.styles.includes(style)
                ? prev.styles.filter(s => s !== style)
                : [...prev.styles, style],
        }));
    };

    const toggleColor = (colorName) => {
        if (!isEditing) return;
        setProfile(prev => ({
            ...prev,
            colors: prev.colors.includes(colorName)
                ? prev.colors.filter(c => c !== colorName)
                : [...prev.colors, colorName],
        }));
    };

    const handleSave = async () => {
        const token = localStorage.getItem('token');
        if (!token) return;
        try {
            await axios.put(`${API_BASE}/profile`, {
                gender: profile.gender || null,
                age: profile.age ? parseInt(profile.age, 10) : null,
                fashion_styles: profile.styles,
                preferred_colors: profile.colors,
                display_name: editedName
            }, {
                headers: { Authorization: `Bearer ${token}` }
            });

            if (editedName.trim() !== displayName) {
                updateUserName(editedName);
            }
            
            setSaved(true);
            setIsEditing(false);
            setTimeout(() => setSaved(false), 2000);
        } catch (error) {
            console.error("Error saving profile", error);
            alert("Failed to save profile. Please try again.");
        }
    };

    const handleDpChange = (e) => {
        const file = e.target.files?.[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onloadend = () => {
            updateUserAvatar(reader.result);
            setSaved(true);
            setTimeout(() => setSaved(false), 2000);
        };
        reader.readAsDataURL(file);
        e.target.value = '';
    };

    return (
        <div className="profile-panel">
            <header className="profile-header">
                <div className="header-content">
                    <h1 className="header-title">
                        {displayName}'s <span className="accent-text">Profile</span>
                    </h1>
                    <p className="header-subtitle">Personalize your style identity and preferences</p>
                </div>
                {!isEditing && (
                    <button className="btn-edit-ghost" onClick={() => setIsEditing(true)}>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                        Edit profile
                    </button>
                )}
            </header>

            <div className="profile-hero">
                <div className="hero-main">
                    <div className="hero-avatar-wrapper">
                        <div className="hero-avatar">
                            {user?.avatar ? (
                                <img src={user.avatar} alt={displayName} className="hero-avatar-img" />
                            ) : (
                                <span className="avatar-initial">{displayName.charAt(0)}</span>
                            )}
                        </div>
                    </div>
                    <div className="hero-info">
                        <h2 className="hero-name">{displayName}</h2>
                        <p className="hero-email">{user?.email}</p>
                    </div>
                </div>

                <div className="stats-row">
                    <div className="stat-card">
                        <span className="stat-value stat-value--accent">{profile.styles.length}</span>
                        <span className="stat-label">STYLES</span>
                    </div>
                    <div className="stat-card">
                        <span className="stat-value stat-value--accent">{profile.colors.length}</span>
                        <span className="stat-label">COLORS</span>
                    </div>
                    <div className="stat-card">
                        <span className="stat-value">{profile.age || '--'}</span>
                        <span className="stat-label">AGE</span>
                    </div>
                </div>
            </div>

            <div className="profile-content-card">
                {isEditing ? (
                    <div className="edit-form-container">
                        <div className="profile-form">
                            <div className="profile-form__row">
                                <div className="profile-form__group profile-form__group--full">
                                    <label className="label">Username</label>
                                    <input
                                        className="input"
                                        placeholder="Enter your name"
                                        value={editedName}
                                        onChange={(e) => setEditedName(e.target.value)}
                                    />
                                </div>
                            </div>
                            <div className="profile-form__row">
                                <div className="profile-form__group">
                                    <label className="label">Gender</label>
                                    <select className="select" value={profile.gender} onChange={handleGenderChange}>
                                        <option value="">Select gender</option>
                                        <option value="male">Male</option>
                                        <option value="female">Female</option>
                                        <option value="other">Other</option>
                                    </select>
                                </div>
                                <div className="profile-form__group">
                                    <label className="label">Age</label>
                                    <input
                                        type="number"
                                        className="input"
                                        placeholder="Enter age"
                                        value={profile.age}
                                        onChange={handleAgeChange}
                                    />
                                </div>
                            </div>
                            <div className="profile-form__group">
                                <label className="label">Style Preferences</label>
                                <div className="chips">
                                    {styleOptions.map(style => (
                                        <button
                                            key={style}
                                            className={`chip ${profile.styles.includes(style) ? 'chip--selected' : ''}`}
                                            onClick={() => toggleStyle(style)}
                                        >
                                            {style}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div className="profile-form__group">
                                <label className="label">Favorite Colors</label>
                                <div className="color-swatches">
                                    {colorOptions.map(color => (
                                        <button
                                            key={color.name}
                                            className={`color-swatch ${profile.colors.includes(color.name) ? 'color-swatch--selected' : ''}`}
                                            style={{ backgroundColor: color.hex }}
                                            onClick={() => toggleColor(color.name)}
                                            title={color.name}
                                        />
                                    ))}
                                </div>
                            </div>
                            <div className="profile-form__actions">
                                <button className="btn btn--secondary" onClick={() => setIsEditing(false)}>Cancel</button>
                                <button className="btn btn--primary" onClick={handleSave}>Save Changes</button>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="view-container">
                        <section className="profile-section">
                            <h3 className="section-title">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="section-icon"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"></rect><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"></path></svg>
                                IDENTITY
                            </h3>
                            <div className="info-grid">
                                <div className="info-item">
                                    <span className="info-label">USERNAME</span>
                                    <span className="info-value">{displayName}</span>
                                </div>
                                <div className="info-item">
                                    <span className="info-label">GENDER</span>
                                    <span className="info-value capitalize">{profile.gender || 'Not specified'}</span>
                                </div>
                            </div>
                        </section>

                        <section className="profile-section">
                            <h3 className="section-title">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="section-icon"><circle cx="12" cy="12" r="10"></circle><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"></path><path d="M2 12h20"></path></svg>
                                STYLE PREFERENCES
                            </h3>
                            <div className="chips-row">
                                {profile.styles.map(style => (
                                    <div key={style} className="info-chip">
                                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20.38 3.46L16 2a4 4 0 0 1-8 0L3.62 3.46a2 2 0 0 0-1.62 1.97V21a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V5.43a2 2 0 0 0-1.62-1.97z"></path><path d="M12 22V12"></path></svg>
                                        {style}
                                    </div>
                                ))}
                                {profile.styles.length === 0 && <span className="empty-text">No styles selected</span>}
                            </div>
                        </section>

                        <section className="profile-section">
                            <h3 className="section-title">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="section-icon"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z"></path></svg>
                                FAVOURITE COLORS
                            </h3>
                            <div className="chips-row">
                                {profile.colors.map(colorName => {
                                    const colorObj = colorOptions.find(c => c.name === colorName);
                                    return (
                                        <div key={colorName} className="info-chip">
                                            <span className="color-dot" style={{ backgroundColor: colorObj?.hex || '#ccc' }}></span>
                                            {colorName}
                                        </div>
                                    );
                                })}
                                {profile.colors.length === 0 && <span className="empty-text">No colors selected</span>}
                            </div>
                        </section>
                    </div>
                )}
            </div>

            <footer className="profile-footer">
                <p className="last-updated">Last updated · {new Date().toLocaleString('en-US', { month: 'long', year: 'numeric' })}</p>
                <div className="footer-action">
                    <button className="btn-down-arrow">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M7 13l5 5 5-5M7 6l5 5 5-5"></path></svg>
                    </button>
                </div>
            </footer>

            {saved && (
                <div className="save-toast">✓ Profile updated successfully</div>
            )}
        </div>
    );
}

export default Profile;
