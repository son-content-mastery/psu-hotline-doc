import forms from '@tailwindcss/forms'
import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#effcf9',
          100: '#d6f6ee',
          600: '#0f766e',
          700: '#0f5f59',
          800: '#124e49',
          900: '#123f3b',
        },
      },
      fontFamily: {
        sans: ['Noto Sans Thai', 'Tahoma', 'Arial', 'sans-serif'],
      },
      boxShadow: {
        card: '0 12px 30px rgba(15, 23, 42, 0.08)',
      },
    },
  },
  plugins: [forms],
} satisfies Config
