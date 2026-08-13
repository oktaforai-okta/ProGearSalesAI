/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // CourtEdge ProGear Basketball Theme
        'primary': '#1a1a2e',        // Deep court black
        'primary-light': '#16213e',  // Court shadow
        'accent': '#ff6b35',         // Basketball orange (primary accent)
        'accent-light': '#ff8c5a',   // Light basketball orange
        'court-orange': '#e85d04',   // Deep basketball orange
        'court-brown': '#8b4513',    // Hardwood court brown
        'court-tan': '#d4a574',      // Light court wood
        'hoop-red': '#c41e3a',       // Basketball hoop red
        'net-white': '#fafafa',      // Net white
        'tech-purple': '#8b5cf6',    // AI/technology purple
        'tech-purple-light': '#a78bfa',
        'okta-blue': '#007dc1',      // Okta brand blue
        'okta-blue-light': '#0ea5e9',
        'success-green': '#22c55e',  // Success states
        'error-red': '#ef4444',      // Error states
        'neutral-bg': '#0d0d14',     // Dark background
        'neutral-border': '#2a2a3e', // Dark borders

        // Agent colors (matching backend)
        'agent-sales': '#3b82f6',     // Blue
        'agent-inventory': '#10b981', // Green
        'agent-customer': '#8b5cf6',  // Purple
        'agent-pricing': '#f59e0b',   // Orange

        // Legacy progear colors (keep for compatibility)
        'progear': {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          800: '#075985',
          900: '#0c4a6e',
        },
      },
      fontFamily: {
        'display': ['Inter', 'system-ui', 'sans-serif'],
        'mono': ['JetBrains Mono', 'Courier New', 'monospace'],
      },
    },
  },
  plugins: [],
};
