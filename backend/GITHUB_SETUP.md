# GitHub Setup & Security Guide: v6.0 Institutional Trading Stack

This guide explains how to safely push your trading system to a GitHub repository while protecting sensitive brokerage data and API keys.

---

## 🛡️ Step 0: Security First (CRITICAL)
Before doing anything, ensure your `.gitignore` file is active. This prevents sensitive files like `.env` (API keys) and `hedge.db` (trade history) from being uploaded to the public internet.

---

## 🚀 Step-by-Step Upload

### 1. Initialize Git
Open a terminal in the project root (`e:\s.y.s.t.e.m`) and run:
```bash
git init
```

### 2. Create a Private Repository
1. Go to [github.com/new](https://github.com/new).
2. Name your repository (e.g., `gold-orderflow-v6`).
3. **IMPORTANT**: Select **`Private`**. NEVER make institutional trading code public.

### 3. Link and Push
In your terminal, run the following (replace `<USERNAME>` and `<REPO>` with your details):
```bash
git add .
git commit -m "Initial commit: v6.0.0 Institutional Core"
git branch -M main
git remote add origin https://github.com/<USERNAME>/<REPO>.git
git push -u origin main
```

---

## ✅ Best Practices for GitHub

### 1. Protect your Secrets
Never commit your `.env` file. Instead, create a `env.example` file with placeholder values so you know what keys are needed on a new machine.

### 2. Branching Strategy
- **`main`**: Only stable, production-ready code.
- **`develop`**: For testing new features (like activating IGOF).

### 3. Use README.md
Your `README.md` is the "face" of your project. Keep it updated with the latest system version and performance metrics.

---

## 🛠️ Typical GitHub Workflow
When you make changes to the system:
```bash
git add .
git commit -m "Update: [Brief description of change]"
git push
```
