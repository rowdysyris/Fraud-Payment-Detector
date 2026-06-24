/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
      },
      colors: {
        ink: '#020617',
        panel: '#0f172a',
        cyanGlow: '#22d3ee',
        violetGlow: '#a855f7',
      },
      boxShadow: {
        glow: '0 0 42px rgba(34, 211, 238, 0.20)',
        violet: '0 0 42px rgba(168, 85, 247, 0.18)',
        card: '0 24px 90px rgba(2, 6, 23, 0.58)',
      },
      keyframes: {
        shimmer: {
          '0%': { transform: 'translateX(-120%)' },
          '100%': { transform: 'translateX(120%)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '0.58' },
          '50%': { opacity: '1' },
        },
      },
      animation: {
        shimmer: 'shimmer 2.2s linear infinite',
        pulseSoft: 'pulseSoft 2.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
