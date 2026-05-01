import streamlit as st

def apply_styles():
    st.markdown("""
    <style>
        /* Premium Obsidian Theme */
        :root {
            --primary-bg: #0f1115;
            --card-bg: rgba(255, 255, 255, 0.03);
            --accent-glow: #3b82f6;
        }
        
        .stApp {
            background-color: var(--primary-bg);
            color: #e5e7eb;
        }
        
        /* Glassmorphism Card Style */
        .metric-card {
            background: var(--card-bg);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }
        
        /* Title Gradient */
        .page-title {
            background: linear-gradient(90deg, #fff 0%, #3b82f6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800;
            font-size: 2rem;
            margin-bottom: 1.5rem;
        }
    </style>
    """, unsafe_allow_html=True)
