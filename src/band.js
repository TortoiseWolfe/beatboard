/**
 * SCRIPTHAMMER BAND
 * Seven steampunk robot musicians from TortoiseWolfe/wp-dev (2025), by Jonathan Pohlner.
 * Portraits: assets/band/*.webp (256px wide, <80KB each).
 * The tool that made the portraits is not recorded.
 */
export const bandMembers = [
  {
    name: 'Ivory',
    instrument: 'Jazz piano and vintage synths',
    role: 'Melody Master',
    personality: 'Serene, cerebral, occasionally mischievous with syncopations',
    look: 'Glossy porcelain-white frame, clean curves, glowing blue inlays, elegant movement'
  },
  {
    name: 'Crash',
    instrument: 'Full drum kit',
    role: 'Pulse Engine',
    personality: 'Energetic, expressive, always in motion like a hyperactive metronome',
    look: 'Compact, spring-loaded limbs, polished brass armor with kinetic glyphs'
  },
  {
    name: 'Chops',
    instrument: 'Franken-guitar',
    role: 'Harmonic Hacker',
    personality: 'Street-smart, sardonic, thrives on chaos and crunchy chords',
    look: 'Punk aesthetic, asymmetrical plating, CRT screen eyes, tangled wires'
  },
  {
    name: 'Reed',
    instrument: 'Alto sax',
    role: 'Lyrical Breeze',
    personality: 'Cool-headed, introspective, speaks through his solos',
    look: 'Slim, chrome body, trench coat detail sculpted into chassis, LED eyes'
  },
  {
    name: 'Brass',
    instrument: 'Trumpet',
    role: 'Frontline Flame',
    personality: 'Showboat, loud and proud, always at the center of a solo',
    look: 'Gleaming gold plating, spotlight-reactive finish, flared armor'
  },
  {
    name: 'Verse',
    instrument: 'Vocoder & Mic',
    role: 'Soul Node',
    personality: 'Passionate, poetic, the most "human" of the bots',
    look: 'Holographic face panel with waveform lips, changing LED mouth'
  },
  {
    name: 'Form',
    instrument: 'Control surface',
    role: 'Architect',
    personality: 'Focused, observant, rarely speaks but always orchestrating',
    look: 'Gunmetal gray with flowing LED matrix, modular appendages'
  }
];

export const logo = {
  name: 'ScriptHammer',
  look: 'ScriptHammer logo, brass gear intertwined with treble clef, steam rising'
};

/**
 * Track-to-musician casting.
 * Tracks 1-4 (Kick, Snare, Hats, Perc) share Crash.
 * Track 5 (Bass) = Chops.
 * Track 6 (Keys) = Ivory.
 * Track 7 (Bed) = Reed.
 * Track 8 (Jingle) = Verse, with Brass beside him.
 * Master/MIX layer = Form.
 */
export const trackCasting = [
  { track: 1, name: 'Kick', musician: 'Crash' },
  { track: 2, name: 'Snare', musician: 'Crash' },
  { track: 3, name: 'Hats', musician: 'Crash' },
  { track: 4, name: 'Perc', musician: 'Crash' },
  { track: 5, name: 'Bass', musician: 'Chops' },
  { track: 6, name: 'Keys', musician: 'Ivory' },
  { track: 7, name: 'Bed', musician: 'Reed' },
  { track: 8, name: 'Jingle', musician: 'Verse', guest: 'Brass' },
  { track: 'master', name: 'Master', musician: 'Form' }
];

export function getMusicianForTrack(trackNum) {
  const entry = trackCasting.find(t => t.track === trackNum);
  if (!entry) return null;
  const musician = bandMembers.find(m => m.name === entry.musician);
  const guest = entry.guest ? bandMembers.find(m => m.name === entry.guest) : null;
  return { musician, guest };
}

export function getMusicianByName(name) {
  return bandMembers.find(m => m.name === name) || null;
}

export function getAllMusicians() {
  return [...bandMembers];
}

export function getPortraitPath(name) {
  return `assets/band/${name.toLowerCase()}.webp`;
}

export function getLogoPath() {
  return 'assets/band/logo.webp';
}