/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#364BA8',
        secondary: '#DF6951',
        light: '#FFFFFF',
      },
    },
  },
  plugins: [],
}
