/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: '1.5rem',
      screens: {
        '2xl': '1400px',
      },
    },
    extend: {
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          '"PingFang SC"',
          '"Hiragino Sans GB"',
          '"Noto Sans SC"',
          '"Microsoft YaHei"',
          'sans-serif',
        ],
        mono: [
          '"JetBrains Mono"',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Monaco',
          'monospace',
        ],
      },
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        cyan: {
          DEFAULT: 'var(--sage)',
          dim: 'color-mix(in srgb, var(--sage) 80%, var(--surface))',
          glow: 'rgb(107 143 113 / 0.24)',
        },
        purple: {
          DEFAULT: 'var(--gold)',
          dim: 'color-mix(in srgb, var(--gold) 80%, var(--surface))',
          glow: 'rgb(212 165 116 / 0.22)',
        },
        success: {
          DEFAULT: 'hsl(var(--success))',
          dim: 'hsl(var(--success) / 0.8)',
          glow: 'hsl(var(--success) / 0.3)',
        },
        warning: {
          DEFAULT: 'hsl(var(--warning))',
          dim: 'hsl(var(--warning) / 0.8)',
          glow: 'hsl(var(--warning) / 0.3)',
        },
        danger: {
          DEFAULT: 'hsl(var(--destructive))',
          dim: 'hsl(var(--destructive) / 0.8)',
          glow: 'hsl(var(--destructive) / 0.3)',
        },
        base: 'hsl(var(--background))',
        elevated: 'hsl(var(--elevated))',
        hover: 'hsl(var(--hover))',
        'secondary-bg': 'hsl(var(--secondary))',
        'muted-bg': 'hsl(var(--muted))',
        'secondary-text': 'hsl(var(--secondary-text))',
        'muted-text': 'hsl(var(--muted-text))',
        // 设计令牌 (Design Tokens)
        dim: 'hsl(var(--border-dim-raw) / 0.06)',
        subtle: 'hsl(var(--bg-subtle-raw) / 0.05)',
        'subtle-hover': 'hsl(var(--bg-subtle-raw) / 0.1)',
        'subtle-soft': 'hsl(var(--bg-subtle-raw) / 0.03)',
        'subtle-active': 'hsl(var(--bg-subtle-raw) / 0.15)',
        'surface-1': 'var(--surface-1)',
        'surface-2': 'var(--surface-2)',
        'surface-3': 'var(--surface-3)',
        'overlay-hover': 'var(--overlay-hover)',
        'overlay-selected': 'var(--overlay-selected)',
      },
      borderColor: {
        dim: 'hsl(var(--border-dim-raw) / 0.06)',
        subtle: 'hsl(var(--border-subtle-raw) / 0.08)',
        'subtle-hover': 'hsl(var(--border-subtle-raw) / 0.15)',
      },
      backgroundColor: {
        subtle: 'hsl(var(--bg-subtle-raw) / 0.05)',
        'subtle-hover': 'hsl(var(--bg-subtle-raw) / 0.1)',
        'subtle-soft': 'hsl(var(--bg-subtle-raw) / 0.03)',
        'subtle-active': 'hsl(var(--bg-subtle-raw) / 0.15)',
      },
      backgroundImage: {
        'gradient-purple-cyan': 'linear-gradient(135deg, rgb(220 231 220 / 0.55) 0%, rgb(255 255 255 / 0.36) 100%)',
        'gradient-card-border': 'linear-gradient(180deg, rgb(107 143 113 / 0.22) 0%, rgb(212 165 116 / 0.16) 100%)',
        'gradient-cyan': 'linear-gradient(135deg, var(--sage) 0%, var(--sage-deep) 100%)',
        'primary-gradient': 'linear-gradient(135deg, var(--sage) 0%, var(--sage-deep) 100%)',
      },
      boxShadow: {
        'soft-card': 'var(--shadow)',
        'glow-cyan': 'var(--shadow-tight)',
        'glow-purple': 'var(--shadow-tight)',
        'glow-success': 'var(--shadow-tight)',
        'glow-danger': 'var(--shadow-tight)',
        'cyan/20': 'var(--shadow-tight)',
        'cyan/22': 'var(--shadow)',
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)',
        xl: '12px',
        '2xl': '16px',
        '3xl': '20px',
      },
      fontSize: {
        xxs: '10px',
        label: '11px',
      },
      spacing: {
        18: '4.5rem',
        22: '5.5rem',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        'spin-slow': 'spin 2s linear infinite',
        'float-in': 'floatIn 0.45s ease-out',
        'ghost-scan': 'ghostScan 3s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          from: { opacity: '0', transform: 'translateX(100%)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        floatIn: {
          from: { opacity: '0', transform: 'translateY(16px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: 'var(--shadow-tight)' },
          '50%': { boxShadow: 'var(--shadow)' },
        },
        ghostScan: {
          '0%': { transform: 'translateY(-110%)', opacity: '0' },
          '20%': { opacity: '0.35' },
          '50%': { transform: 'translateY(28%)', opacity: '0.16' },
          '100%': { transform: 'translateY(135%)', opacity: '0' },
        },
      },
    },
  },
  plugins: [],
};
