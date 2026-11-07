/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bank: {
          DEFAULT: '#334155',
          dark: '#0f172a',
          light: '#64748b'
        },
        daily: {
          DEFAULT: '#059669',
          dark: '#064e3b',
          light: '#34d399'
        },
        freedom: {
          DEFAULT: '#7c3aed',
          dark: '#4c1d95',
          light: '#a78bfa'
        },
        vault: {
          DEFAULT: '#d97706',
          dark: '#78350f',
          light: '#fbbf24'
        },
        bills: {
          DEFAULT: '#0284c7',
          dark: '#0c4a6e',
          light: '#38bdf8'
        }
      }
    },
  },
  plugins: [],
}
