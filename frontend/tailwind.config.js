/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        delhi: {
          primary: '#0F766E', // Teal / Green representing Delhi bus fleet
          secondary: '#1E293B', // Slate dark
          accent: '#0284C7', // Sky blue
          warning: '#D97706', // Amber warning for expired timetable
          alert: '#DC2626', // Red for errors / offline
          surface: '#F8FAFC',
          card: '#FFFFFF',
          border: '#E2E8F0',
        }
      }
    },
  },
  plugins: [],
}

