/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 云控制台主题色
        console: {
          bg: '#0d1117',
          surface: '#161b22',
          border: '#30363d',
          primary: '#238636',
          accent: '#1f6feb',
          warning: '#d29922',
          error: '#f85149',
          text: '#c9d1d9',
          'text-muted': '#8b949e',
        },
        // 代码背景色
        code: {
          bg: '#0d1117',
        },
        // 保留旧主题兼容
        primary: {
          50: '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
        },
        pouw: {
          dark: '#0d1117',
          purple: '#1f6feb',
          blue: '#238636',
          accent: '#58a6ff',
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Monaco', 'monospace'],
      },
      fontSize: {
        'xxs': '0.625rem',
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    },
  },
  plugins: [],
}

