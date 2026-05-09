/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'kg-dark': '#0B0E14',
        'kg-surface': 'rgba(255, 255, 255, 0.02)',
        'kg-panel': 'rgba(255, 255, 255, 0.03)',
        'kg-border': 'rgba(255, 255, 255, 0.05)',
        'kg-gold': '#5D5FEF', /* Neon purple for primary actions */
        'kg-accent': '#00F0FF', /* Electric cyan */
        'kg-success': '#00E676', /* Neon green */
        'kg-danger': '#FF2A55', /* Neon pink/red */
        'kg-muted': '#6B7280',
        'kg-text': '#F3F4F6',
      },
      fontFamily: {
        'mono': ['JetBrains Mono', 'monospace'],
        'inter': ['Inter', 'sans-serif'],
      },
      fontSize: {
        'xs': ['0.75rem', { lineHeight: '1rem' }],
        'sm': ['0.875rem', { lineHeight: '1.25rem' }],
        'base': ['1rem', { lineHeight: '1.5rem' }],
        'lg': ['1.125rem', { lineHeight: '1.75rem' }],
        'xl': ['1.25rem', { lineHeight: '1.75rem' }],
        '2xl': ['1.5rem', { lineHeight: '2rem' }],
      },
      keyframes: {
        'pulse-gold': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
        'flash-up': {
          '0%': { color: '#00C896', opacity: '1' },
          '100%': { color: 'inherit', opacity: '1' },
        },
        'flash-down': {
          '0%': { color: '#FF3B5C', opacity: '1' },
          '100%': { color: 'inherit', opacity: '1' },
        },
        'slide-in': {
          'from': { opacity: '0', transform: 'translateY(10px)' },
          'to': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'pulse-gold': 'pulse-gold 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'flash-up': 'flash-up 0.3s ease-out',
        'flash-down': 'flash-down 0.3s ease-out',
        'slide-in': 'slide-in 0.15s ease-out',
      },
    },
  },
  plugins: [],
}
