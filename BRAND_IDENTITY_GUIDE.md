# RoyalVista Tech Solutions - Brand Identity Guide

## 🎨 Brand Overview

**Company Name**: RoyalVista Tech Solutions  
**Tagline**: Premium Quality. Unmatched Speed.  
**Industry**: Digital Solutions & Tech Services  
**Brand Personality**: Premium, Innovative, Professional, Fast, Reliable

---

## 🎯 Logo Variations

### 1. **Primary Logo** (Dark Background)
- **File**: `royalvista_logo_main.png`
- **Usage**: Website header, dark backgrounds, primary branding
- **Background**: Dark (#0d0d0d to #1a1a1a)
- **Format**: Horizontal layout with icon + text

### 2. **Favicon**
- **File**: `royalvista_favicon.png`
- **Usage**: Browser tabs, bookmarks, mobile home screen
- **Sizes Needed**: 16x16, 32x32, 64x64, 128x128, 256x256
- **Format**: Square, simplified icon

### 3. **Icon Only**
- **File**: `royalvista_icon_only.png`
- **Usage**: Social media profiles, app icons, watermarks
- **Format**: Square (1024x1024 recommended)
- **Background**: Transparent or dark

### 4. **Light Version**
- **File**: `royalvista_logo_light.png`
- **Usage**: Documents, presentations, light-themed materials
- **Background**: White or light gray (#f4f4f4)

---

## 🎨 Color Palette

### Primary Colors
```css
--primary-color: #6C63FF;      /* Vibrant Purple */
--primary-hover: #5a52d5;      /* Darker Purple */
--secondary-color: #03DAC6;    /* Cyan/Teal */
--accent-gradient: linear-gradient(135deg, #6C63FF 0%, #03DAC6 100%);
```

### Background Colors
```css
--bg-color: #0d0d0d;           /* Main Dark Background */
--bg-darker: #050505;          /* Darker Sections */
--card-bg: #1a1a1a;            /* Card/Panel Background */
--nav-bg: rgba(13, 13, 13, 0.95); /* Navigation Bar */
```

### Text Colors
```css
--text-color: #e0e0e0;         /* Primary Text */
--text-muted: #a0a0a0;         /* Secondary Text */
--text-white: #ffffff;         /* Headings */
```

### Utility Colors
```css
--border-color: #333;          /* Borders */
--shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
```

### Color Usage Guidelines
- **Purple (#6C63FF)**: Primary actions, CTAs, highlights, links
- **Cyan (#03DAC6)**: Secondary accents, icons, success states
- **Gradient**: Hero sections, buttons, special elements
- **Dark Backgrounds**: Main content areas, cards
- **Light Text**: All text on dark backgrounds

---

## 📝 Typography

### Font Families
```css
--font-heading: 'Outfit', sans-serif;  /* Headings, Logo */
--font-body: 'Inter', sans-serif;      /* Body text, UI */
```

### Font Sizes
```css
h1: 3.5rem (56px)    /* Hero titles */
h2: 2.5rem (40px)    /* Section titles */
h3: 1.5rem (24px)    /* Card titles */
p:  1rem (16px)      /* Body text */
small: 0.9rem (14px) /* Captions, metadata */
```

### Font Weights
- **Headings**: 700 (Bold)
- **Buttons**: 600 (Semi-bold)
- **Body**: 400 (Regular)
- **Muted**: 500 (Medium)

### Typography Rules
- Use **Outfit** for all headings, logo, and brand elements
- Use **Inter** for body text, forms, and UI elements
- Maintain 1.6 line-height for readability
- Use gradient text for highlighted words (`.highlight` class)

---

## 🖼️ Logo Usage Guidelines

### Do's ✅
- Use on dark backgrounds (#0d0d0d or darker)
- Maintain minimum clear space (equal to icon height)
- Use provided color versions only
- Scale proportionally
- Use high-resolution files for print

### Don'ts ❌
- Don't distort or stretch the logo
- Don't change colors outside brand palette
- Don't add effects (shadows, outlines, etc.)
- Don't place on busy backgrounds
- Don't use low-resolution files

### Minimum Sizes
- **Web**: 150px width minimum
- **Print**: 1 inch width minimum
- **Favicon**: 16px (use simplified version)
- **Social Media**: 400px square minimum

---

## 🌐 Web Implementation

### HTML Meta Tags
```html
<!-- Favicon -->
<link rel="icon" type="image/png" sizes="32x32" href="/static/assets/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/static/assets/favicon-16x16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/static/assets/apple-touch-icon.png">

<!-- Page Title Format -->
<title>Page Name - RoyalVista Tech Solutions</title>

<!-- Meta Description -->
<meta name="description" content="Premium digital solutions with unmatched quality and speed. Web design, branding, video editing, and more.">

<!-- Open Graph (Social Media) -->
<meta property="og:title" content="RoyalVista Tech Solutions">
<meta property="og:description" content="Premium Quality. Unmatched Speed.">
<meta property="og:image" content="/static/assets/og-image.png">
<meta property="og:type" content="website">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="RoyalVista Tech Solutions">
<meta name="twitter:description" content="Premium Quality. Unmatched Speed.">
<meta name="twitter:image" content="/static/assets/twitter-card.png">
```

### CSS Classes
```css
/* Logo in Navigation */
.logo {
    font-size: 1.8rem;
    font-weight: 700;
    font-family: var(--font-heading);
    color: #fff;
}

/* Highlighted Text */
.highlight {
    color: var(--primary-color);
    background: var(--accent-gradient);
    background-clip: text;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

/* Primary Button */
.btn-primary {
    background: var(--accent-gradient);
    color: #fff;
    padding: 0.8rem 2rem;
    border-radius: 50px;
    font-weight: 600;
}
```

---

## 📱 Social Media Specifications

### Profile Pictures
- **Format**: Square (icon only version)
- **Size**: 1024x1024px minimum
- **File**: `royalvista_icon_only.png`

### Cover Photos
- **Facebook**: 820 x 312px
- **Twitter**: 1500 x 500px
- **LinkedIn**: 1584 x 396px
- **YouTube**: 2560 x 1440px

### Post Images
- **Instagram**: 1080 x 1080px (square)
- **Facebook**: 1200 x 630px
- **Twitter**: 1200 x 675px
- **LinkedIn**: 1200 x 627px

---

## 🎯 Brand Voice & Messaging

### Tone
- **Professional** yet **approachable**
- **Confident** but not arrogant
- **Innovative** and **forward-thinking**
- **Premium** quality focus

### Key Messages
- "Premium Quality. Unmatched Speed."
- "Empowering Brands with Innovation"
- "Digital Solutions That Deliver"
- "Your Vision, Our Expertise"

### Prohibited Phrases
- "Cheap" or "budget"
- "Discount" or "sale"
- "Good enough"
- Anything implying low quality

---

## 📄 File Organization

### Recommended Structure
```
/static/assets/branding/
├── logos/
│   ├── royalvista-logo-dark.png
│   ├── royalvista-logo-light.png
│   ├── royalvista-logo-dark.svg
│   └── royalvista-logo-light.svg
├── icons/
│   ├── royalvista-icon.png
│   ├── royalvista-icon.svg
│   └── royalvista-icon-transparent.png
├── favicons/
│   ├── favicon-16x16.png
│   ├── favicon-32x32.png
│   ├── favicon-64x64.png
│   ├── apple-touch-icon.png
│   └── favicon.ico
└── social/
    ├── og-image.png (1200x630)
    ├── twitter-card.png (1200x675)
    └── profile-picture.png (1024x1024)
```

---

## 🚀 Quick Start Checklist

### Website Implementation
- [ ] Add favicon to `<head>` section
- [ ] Update logo in navigation
- [ ] Add Open Graph meta tags
- [ ] Update page titles format
- [ ] Ensure color consistency
- [ ] Test on dark and light backgrounds

### Social Media Setup
- [ ] Update profile pictures (all platforms)
- [ ] Update cover photos
- [ ] Add brand colors to bio/about sections
- [ ] Use consistent messaging

### Print Materials
- [ ] Use high-resolution logo files
- [ ] Maintain color accuracy (CMYK for print)
- [ ] Follow minimum size guidelines
- [ ] Include tagline when space allows

---

## 📞 Brand Assets Contact

For custom sizes, formats, or brand inquiries:
**Email**: royalvistatechsolutions@gmail.com

---

**Last Updated**: January 2026  
**Version**: 1.0  
**Created for**: RoyalVista Tech Solutions
