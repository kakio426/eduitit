/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./templates/**/*.html",
        "./**/templates/**/*.html",
        "./**/static/**/*.js",
    ],
    theme: {
        extend: {
            colors: {
                'bg-soft': '#E0E5EC',
                'clay-text': '#495057',
            },
            fontFamily: {
                'sans': ['NanumSquareRound', 'Inter', 'sans-serif'],
                'round': ['NanumSquareRound', 'sans-serif'],
                'hand': ['Dongle', 'sans-serif'],
            },
            boxShadow: {
                'clay': '9px 9px 16px rgb(163,177,198,0.6), -9px -9px 16px rgba(255,255,255, 0.5)',
                'clay-inner': 'inset 6px 6px 10px 0 rgba(163, 177, 198, 0.7), inset -6px -6px 10px 0 rgba(255, 255, 255, 0.8)',
                'clay-hover': '12px 12px 24px rgba(163, 177, 198, 0.8), -12px -12px 24px rgba(255, 255, 255, 0.7)',
            },
            borderRadius: {
                'clay': '30px',
            }
        },
    },
    plugins: [],
}
