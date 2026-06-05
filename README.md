## 🌐 Live Demo

**Try FitFlow:** [https://fitflow-beta-tan.vercel.app/](https://fitflow-beta-tan.vercel.app/)

| | |
|---|---|
| **Email** | `ghoshsoumadip62@gmail.com` |
| **Password** | `20262027` |

> Use the credentials above to log in and explore the wardrobe, outfit builder, and AI stylist features.

---

# 👔 FitFlow — AI Virtual Wardrobe Stylist

FitFlow is an **AI-powered virtual wardrobe assistant** that digitizes your clothing collection and generates **context-aware, explainable outfit recommendations**.

It combines **computer vision, rule-based scoring, and generative AI** to help users decide:

* 👕 What to wear
* 🧠 Why it works
* ✨ How to improve it

---

## 🚀 Features

### 📸 Smart Clothing Detection

* Upload an image → Automatically detects clothing type using YOLOv8

### 🎨 Color Extraction

* Extracts dominant color using OpenCV + KMeans

### 🧥 Digital Wardrobe

* Stores clothing items with metadata (type, color, image)

### 👗 Intelligent Outfit Builder

* Generates outfits based on:

  * Occasion (Office, Casual, Party, etc.)
  * Style compatibility
  * Color harmony

### 🧠 Deterministic Scoring Engine

* Evaluates outfits using a **100-point system**:

  * Occasion Fit (50)
  * Style Compatibility (20)
  * Combination Logic (15)
  * Color Harmony (15)

### ⭐ User-Friendly Rating

* Internal score (0–100) → Converted to UI rating (0–10)
* Example: `85 → 8.5/10`

### 🤖 AI Stylist (Groq - LLaMA 3)

* Provides:

  * Outfit explanations
  * Styling issues
  * Improvement suggestions

### 💬 AI Stylist Chat

* Ask:

  * “What should I wear for a date?”
  * “Does this outfit look good?”

### 🧺 Smart Laundry Tracker

* Tracks usage of clothing items
* Encourages wardrobe rotation

### 🛍️ Shopping Suggestions

* Detects missing items
* Fetches real-time product recommendations

### 🧼 Background Removal

* Clean clothing cutouts using Remove.bg

---

## 🏗️ Architecture

```
Frontend (React + Vite)
        ↓
Backend API (FastAPI)
        ↓
ML Layer (YOLOv8 + OpenCV)
        ↓
Rule Engine (Scoring System)
        ↓
LLM Layer (Groq - LLaMA 3)
        ↓
Database (MongoDB) + Storage (Cloudinary)
        ↓
External APIs (Remove.bg + SerpApi)
```

---

## 🧠 Tech Stack

### Frontend

* React.js
* Vite
* CSS (custom styling)

### Backend

* Python
* FastAPI
* REST APIs
* JWT Authentication

### Machine Learning

* YOLOv8 (Object Detection)
* OpenCV (Image Processing)
* KMeans (Color Extraction)

### AI (Generative Layer)

* Groq (LLaMA 3 70B)

### Database & Storage

* MongoDB Atlas
* Cloudinary

### Integrations

* Remove.bg API
* SerpApi

---

## 🔄 How It Works

### 1. Upload Clothing

* User uploads an image
* Background is removed
* YOLO detects clothing category
* OpenCV extracts color
* Data is stored

### 2. Generate Outfit

* User selects occasion
* Backend generates combinations

### 3. Scoring

* Outfit evaluated using rule-based engine (0–100)
* Converted to UI rating (0–10)

### 4. AI Feedback

* LLM generates:

  * Explanation
  * Issues
  * Suggestions

### 5. Shopping Suggestions

* Missing items detected
* Products fetched via API

---

## 🧮 Scoring System

```
Total Score = 100

Occasion Fit        → 50
Style Compatibility → 20
Combination Logic   → 15
Color Harmony       → 15
```

### Conversion

```
UI Rating = Score / 10
```

### Example Rules

* ❌ Sneakers in formal → penalty
* ❌ Shorts in office → invalid
* ✅ Blazer + formal shirt → high score
* ✅ T-shirt + jeans → strong casual match

---

## 📦 Project Structure

```
fitflow/
│
├── frontend/          # React app
├── backend/
│   ├── main.py        # FastAPI entry point
│   ├── routes/        # API endpoints
│   ├── services/      # Business logic
│   ├── models/        # ML models
│   ├── recommender.py # Scoring engine
│   └── ai_service.py  # LLM integration
│
├── database/          # MongoDB schema
├── utils/             # Image utilities
└── README.md
```

---

## ⚙️ Setup

### Clone Repository

```bash
git clone https://github.com/your-username/fitflow.git
cd fitflow
```

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

---

## 🔑 Environment Variables

Create `.env` in backend:

```
MONGO_URI=your_mongodb_uri
CLOUDINARY_URL=your_cloudinary_url
REMOVE_BG_API_KEY=your_key
SERP_API_KEY=your_key
GROQ_API_KEY=your_key
JWT_SECRET=your_secret
```

---

## 📈 Future Improvements

* Personalized recommendations (user preference learning)
* ML-based ranking system
* Weather-based outfit suggestions
* Redis caching for faster responses
* Mobile application
* Pattern & texture detection

---

## 🧪 Challenges

* Handling real-world messy images
* Extracting accurate colors under varying lighting
* Designing a balanced scoring system
* Combining rule-based logic with LLM outputs
* Managing async image workflows

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Open a pull request

---

## 📄 License

This project is licensed under the MIT License.

---

## ⭐ Summary

FitFlow combines:

* Computer Vision
* Rule-based reasoning
* Generative AI

to build an **explainable, personalized fashion recommendation system**.



---
