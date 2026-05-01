/**
 * generate_icon.js
 * Generates app icons from SVG for Tauri
 * Run: node generate_icon.js
 * 
 * Requires: npm install sharp
 */

import sharp from 'sharp';
import { writeFileSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// SVG content (exact from BrandLogo.jsx)
const svgContent = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <filter id="cyan-glow">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
    <filter id="green-glow">
      <feGaussianBlur stdDeviation="2" result="blur"/>
      <feComposite in="SourceGraphic" in2="blur" operator="over"/>
    </filter>
    <clipPath id="hex-clip">
      <polygon points="256,40 450,152 450,360 256,472 62,360 62,152"/>
    </clipPath>
  </defs>
  <rect width="512" height="512" fill="#000000"/>
  <polygon points="256,40 450,152 450,360 256,472 62,360 62,152" fill="#050505" stroke="#00c8f0" stroke-width="3" filter="url(#cyan-glow)"/>
  <polygon points="256,60 432,162 432,350 256,452 80,350 80,162" fill="none" stroke="#00c8f0" stroke-width="0.5" opacity="0.2"/>
  <g clip-path="url(#hex-clip)">
    <line x1="62" y1="200" x2="450" y2="200" stroke="#1a1a1a" stroke-width="0.5"/>
    <line x1="62" y1="256" x2="450" y2="256" stroke="#1a1a1a" stroke-width="0.5"/>
    <line x1="62" y1="312" x2="450" y2="312" stroke="#1a1a1a" stroke-width="0.5"/>
    <line x1="160" y1="40" x2="160" y2="472" stroke="#1a1a1a" stroke-width="0.5"/>
    <line x1="256" y1="40" x2="256" y2="472" stroke="#1a1a1a" stroke-width="0.5"/>
    <line x1="352" y1="40" x2="352" y2="472" stroke="#1a1a1a" stroke-width="0.5"/>
    <line x1="168" y1="190" x2="168" y2="222" stroke="#ff2d4e" stroke-width="2"/>
    <rect x="158" y="222" width="20" height="58" fill="#ff2d4e" rx="1"/>
    <line x1="168" y1="280" x2="168" y2="310" stroke="#ff2d4e" stroke-width="2"/>
    <line x1="238" y1="175" x2="238" y2="210" stroke="#00e87a" stroke-width="2"/>
    <rect x="228" y="230" width="20" height="60" fill="#00e87a" rx="1"/>
    <line x1="238" y1="210" x2="238" y2="230" stroke="#00e87a" stroke-width="2" opacity="0.4"/>
    <line x1="238" y1="290" x2="238" y2="320" stroke="#00e87a" stroke-width="2"/>
    <line x1="318" y1="155" x2="318" y2="195" stroke="#00e87a" stroke-width="2"/>
    <rect x="308" y="195" width="20" height="80" fill="#00e87a" rx="1"/>
    <line x1="318" y1="275" x2="318" y2="305" stroke="#00e87a" stroke-width="2"/>
    <rect x="118" y="348" width="8" height="8" fill="#00c8f0" filter="url(#cyan-glow)"/>
    <line x1="122" y1="352" x2="200" y2="352" stroke="#00c8f0" stroke-width="2" filter="url(#cyan-glow)"/>
    <rect x="196" y="222" width="8" height="8" fill="#00c8f0" filter="url(#cyan-glow)"/>
    <line x1="200" y1="352" x2="200" y2="226" stroke="#00c8f0" stroke-width="2" filter="url(#cyan-glow)"/>
    <line x1="200" y1="226" x2="310" y2="226" stroke="#00c8f0" stroke-width="2" filter="url(#cyan-glow)"/>
    <rect x="306" y="148" width="8" height="8" fill="#00c8f0" filter="url(#cyan-glow)"/>
    <line x1="310" y1="226" x2="310" y2="152" stroke="#00c8f0" stroke-width="2" filter="url(#cyan-glow)"/>
    <line x1="310" y1="152" x2="390" y2="152" stroke="#00c8f0" stroke-width="2" filter="url(#cyan-glow)"/>
    <rect x="386" y="148" width="8" height="8" fill="#00c8f0" filter="url(#cyan-glow)"/>
    <path d="M370,340 L370,310 Q370,305 375,303 L395,296 L415,303 Q420,305 420,310 L420,340 Q420,358 395,368 Q370,358 370,340 Z" fill="none" stroke="#445566" stroke-width="1.5" opacity="0.5"/>
    <line x1="395" y1="308" x2="395" y2="355" stroke="#445566" stroke-width="1" opacity="0.3"/>
    <line x1="378" y1="325" x2="412" y2="325" stroke="#445566" stroke-width="1" opacity="0.3"/>
  </g>
  <polygon points="256,40 450,152 450,360 256,472 62,360 62,152" fill="none" stroke="#00c8f0" stroke-width="3" filter="url(#cyan-glow)"/>
  <line x1="256" y1="40" x2="256" y2="55" stroke="#00c8f0" stroke-width="2" opacity="0.6"/>
  <line x1="256" y1="457" x2="256" y2="472" stroke="#00c8f0" stroke-width="2" opacity="0.6"/>
</svg>`;

// Icons to generate
const icons = [
  { name: '32x32.png', size: 32 },
  { name: '128x128.png', size: 128 },
  { name: '256x256.png', size: 256 },
  { name: 'app-icon.png', size: 512 },
];

async function generateIcons() {
  const iconDir = join(__dirname, 'src-tauri', 'icons');
  
  // Ensure directory exists
  if (!existsSync(iconDir)) {
    mkdirSync(iconDir, { recursive: true });
  }
  
  console.log('Generating icons...');
  
  for (const icon of icons) {
    const outputPath = join(iconDir, icon.name);
    
    await sharp(Buffer.from(svgContent))
      .resize(icon.size, icon.size)
      .png()
      .toFile(outputPath);
    
    console.log(`Created: ${icon.name} (${icon.size}x${icon.size})`);
  }
  
  console.log('Icon generation complete!');
}

generateIcons().catch(console.error);