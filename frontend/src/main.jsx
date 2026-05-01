// main.jsx - Application entry point
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';

// Google Fonts
const fontLink = document.createElement('link');
fontLink.href = 'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Syne:wght@700;800&display=swap';
fontLink.rel = 'stylesheet';
document.head.appendChild(fontLink);

// Render app
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);