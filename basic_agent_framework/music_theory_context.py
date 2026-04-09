"""
music_theory_context.py
-----------------------
Open Music Theory chapter content, stored as string constants and assembled
into per-agent context blocks for in-context learning.

Sources: https://openmusictheory.github.io/contents.html
  - harmonicFunctions.html
  - harmonicSyntax1.html  (The Idealized Phrase)
  - harmonicSyntax2.html  (Prolongation)
  - cadenceTypes.html
  - alteredSubdominants.html
  - appliedChords.html
"""

# ──────────────────────────────────────────────────────────────────────────────
# Chapter: Harmonic Functions in Tonal Music
# Source: https://openmusictheory.github.io/harmonicFunctions.html
# ──────────────────────────────────────────────────────────────────────────────

HARMONIC_FUNCTIONS = """
# Harmonic Functions in Tonal Music

A harmonic function describes the role that a particular chord plays in creating
a larger harmonic progression. Chords exhibit tendencies toward certain progressions
and musical contexts, creating meaningful harmonic structures that support phrases.

## Three Primary Functions

In common-practice music (Bach, Mozart, Haydn, etc.), chords cluster into three
functional categories based on their scale degrees:

**Tonic (T):** Characteristic scale degrees 1, 3, 5, 6, 7
  - Chords: I, III, VI
  - Feeling of rest, stability, arrival

**Subdominant / Pre-Dominant (S or PD):** Characteristic scale degrees 1, 2, 3, 4, 6
  - Chords: II, IV
  - Feeling of departure, moving away from tonic toward dominant

**Dominant (D):** Characteristic scale degrees 2, 4, 5, 6, 7
  - Chords: V, VII
  - Feeling of tension and instability, strong pull toward tonic

## Functional Cycle
The fundamental progression follows: T → S → D → T (tonic → subdominant → dominant → tonic)
This cycle creates the sense of harmonic motion and resolution that defines tonal music.

## Roman Numeral Labels
Place Roman numerals below the bass line with functional labels underneath:
  - I   = Tonic (T)
  - ii  = Subdominant/Pre-Dominant (S)
  - IV  = Subdominant/Pre-Dominant (S)
  - V   = Dominant (D)
  - V7  = Dominant seventh (D)
  - vii°= Dominant (D)
  - vi  = Tonic (T) — often used as a tonic substitute

## Inversions (Figured Bass)
  - Root position: no number needed (or 5/3)
  - First inversion: 6  (e.g., I6, ii6, V6)
  - Second inversion: 6/4  (e.g., I6/4, cadential 6/4)
  - Seventh chord first inversion: 6/5
  - Seventh chord second inversion: 4/3
  - Seventh chord third inversion: 4/2 or 2
"""

# ──────────────────────────────────────────────────────────────────────────────
# Chapter: Harmonic Syntax — The Idealized Phrase
# Source: https://openmusictheory.github.io/harmonicSyntax1.html
# ──────────────────────────────────────────────────────────────────────────────

HARMONIC_SYNTAX_PHRASE = """
# Harmonic Syntax: The Idealized Phrase

Harmonic syntax concerns the principles governing which chord progressions are
idiomatic and meaningful in common-practice Western music.

## The Functional Cycle
The most fundamental progression: T → S → D → T
This models the journey from rest (tonic), through departure (subdominant),
through tension (dominant), back to rest (tonic).

## The Idealized Phrase Structure
A complete phrase typically follows this shape:
  1. Opening tonic (stability)
  2. Pre-dominant / subdominant chords (departure)
  3. Dominant harmony (tension)
  4. Final tonic with authentic cadence (resolution)

Examples:
  - Simple: I – V – I
  - Expanded: I – IV – V – I
  - With more harmony: I – vi – ii – V7 – I

## Rules for Harmonic Progression
  - Tonic may go to any function (T → S, T → D, or T → T)
  - Pre-dominant progresses to dominant (S → D)
  - Dominant progresses to tonic (D → T), or deceptively to vi (D → vi)
  - Avoid backward motion in the cycle: D → S is very rare

## Common Chord Progressions in Bach Chorales
  - I – V6 – I  (tonic prolongation with passing bass)
  - I – IV – V – I  (complete T-S-D-T)
  - I – ii6 – V7 – I  (ii6 as pre-dominant, very common in Bach)
  - I – vi – IV – V – I  (extended opening)
  - V6/4 – V – I  (cadential 6/4 resolving to V then I)
"""

# ──────────────────────────────────────────────────────────────────────────────
# Chapter: Harmonic Syntax — Prolongation
# Source: https://openmusictheory.github.io/harmonicSyntax2.html
# ──────────────────────────────────────────────────────────────────────────────

HARMONIC_SYNTAX_PROLONGATION = """
# Harmonic Syntax: Prolongation

Prolongation techniques extend a single harmonic function across multiple chords.
The chord changes, but the underlying harmonic function stays the same.

## Prolongation Techniques

### Change-of-Figure Prolongation
The bass stays constant, but upper voices change (or a chord quality shifts).
  Examples: V → V7 (both dominant), IV → ii6 (both subdominant)

### Change-of-Bass Prolongation
Two chords with the same function appear with different bass notes.
  Examples: I → I6 (tonic), IV → ii (subdominant), V → V6 (dominant)

### Passing Chord Prolongation
A chord fills a stepwise bass motion between two chords of the same function.
  Pattern: I – V6/4 – I6  (V6/4 passes between I and I6, prolonging tonic)
  Note: passing V6/4 is different from the cadential I6/4!

### Neighbor Chord Prolongation
A chord returns to the same bass note after briefly moving away (neighbor tone).
  Example: I – V7 – I  (V7 briefly neighbors I)
  Example: I – IV – I  (plagal neighbor, IV neighbors I)

### Divider Prolongation
A chord subdivides a large bass leap.
  Example: I – V – I  (V divides the octave)

## Key Rule for Analysis
When you see multiple chords in a row, ask:
  1. Do they share the same harmonic function? → Prolongation
  2. Or do they move through T-S-D-T? → Functional progression
"""

# ──────────────────────────────────────────────────────────────────────────────
# Chapter: Classical Cadence Types
# Source: https://openmusictheory.github.io/cadenceTypes.html
# ──────────────────────────────────────────────────────────────────────────────

CADENCE_TYPES = """
# Classical Cadence Types

A cadence marks a point of arrival that punctuates the end of a musical unit
(phrase, theme, section, or movement). It combines harmonic, melodic, and rhythmic elements.

## Authentic Cadences (V → I)
End with a V–I motion in the bass.

### Perfect Authentic Cadence (PAC)
  - Both V and I are in root position
  - Melody ends on scale degree 1 (do)
  - Strongest, most conclusive cadence type
  - Used at end of periods, sections, and movements

### Imperfect Authentic Cadence (IAC)
  - V–I progression, but melody ends on 3 (mi) or 5 (sol), OR
  - One of the chords is inverted
  - Less conclusive than PAC

## Half Cadence (HC)
  - Phrase ends on V (does NOT resolve to I)
  - V is usually in root position
  - Melody often has scale degree 2 (re) at the cadence
  - Creates a sense of pause and expectation — "musical question mark"
  - Very common at the end of antecedent phrases

## Deceptive Cadence (DC)
  - V resolves to vi instead of I (in major)
  - V resolves to VI instead of i (in minor)
  - vi is a tonic substitute — sounds unexpected but still resolves

## Plagal Cadence (PC)
  - IV → I motion (subdominant to tonic)
  - The "Amen" cadence in hymns
  - Often used after an authentic cadence as a reinforcement

## Cadence Formula in Bach Chorales
Bach most commonly uses:
  - ii6 – V – I  (pre-dominant → dominant → tonic) for PAC
  - ii6 – V  (stopping on V) for HC
  - V7 – I  for strong conclusive endings
  - Cadential 6/4: I6/4 – V – I  (the I6/4 is NOT a tonic chord — it's a dominant preparation!)
"""

# ──────────────────────────────────────────────────────────────────────────────
# Chapter: Chromatically Altered Subdominant Chords
# Source: https://openmusictheory.github.io/alteredSubdominants.html
# ──────────────────────────────────────────────────────────────────────────────

ALTERED_SUBDOMINANT_CHORDS = """
# Chromatically Altered Subdominant Chords

These chords substitute for or intensify the subdominant (pre-dominant) function
by using chromatic alterations. The most common are the Neapolitan and augmented-sixth chords.

## Neapolitan Chord (N or N6)
  - Contains lowered 2nd, 4th, and lowered 6th scale degrees
  - Appears as a major triad, almost always in first inversion (N6)
  - Bass note is scale degree 4; scale degree 4 is doubled in 4-voice writing
  - Function: Subdominant (S), leading strongly to V
  - Common in minor keys; also used in major
  - Progression: N6 → V (or N6 → cadential 6/4 → V)

## Augmented-Sixth Chords
All augmented-sixth chords contain both le (♭6) in the bass and fi (♯4),
creating an augmented sixth interval that expands outward to an octave (resolving to 5).

### Italian Augmented-Sixth (It.6)
  - Members: le (♭6), do (1), fi (♯4)  —  three-note chord
  - Bass: le (♭6), doubled: do (1)
  - Resolves: le → sol, fi → sol (both move to dominant 5)
  - Notation: It.6

### French Augmented-Sixth (Fr.6)
  - Members: le (♭6), do (1), re (2), fi (♯4)  —  four-note chord
  - Bass: le (♭6)
  - Most dissonant of the three common types
  - Notation: Fr.6 (or Fr.4/3 figured bass)

### German Augmented-Sixth (Ger.6)
  - Members: le (♭6), do (1), me (♭3), fi (♯4)  —  four-note chord
  - Bass: le (♭6)
  - Almost always followed by cadential 6/4 (to avoid parallel fifths)
  - Most common in minor keys
  - Notation: Ger.6 (or Ger.6/5 figured bass)
"""

# ──────────────────────────────────────────────────────────────────────────────
# Chapter: Applied (Secondary) Chords
# Source: https://openmusictheory.github.io/appliedChords.html
# ──────────────────────────────────────────────────────────────────────────────

APPLIED_CHORDS = """
# Applied Chords (Secondary Dominants and Leading-Tone Chords)

## Core Concept: Tonicization
Tonicization temporarily emphasizes a non-tonic chord by borrowing chords from
the key where that chord IS the tonic. Unlike a full modulation, tonicization
is brief and does not involve a cadence in the new key.

## Mechanism
Any chord (except diminished or augmented triads) can be tonicized by preceding
it with its own dominant (V) or leading-tone chord (vii°).

## Notation
Use slash notation: V/V means "the dominant of the dominant"
  - V/V  = dominant of V  (raises scale degree 4 to create a leading tone to 5)
  - V7/V = dominant seventh of V
  - V/IV = dominant of IV
  - vii°/V = leading-tone chord of V (also very common)

## Common Applied Chords in Bach Chorales
  - V/V  → V   (very common, raises ^4 to create ^#4 as leading tone to ^5)
  - V7/IV → IV  (creates a momentary emphasis on IV)
  - vii°7/V → V  (diminished seventh resolving to V)

## Voice Leading Rules
  - The chromatically raised tone (leading tone of the tonicized chord) must resolve upward by half-step
  - The seventh (if present) must resolve downward by step
  - Applied chords alter the function preceding the tonicized chord:
    altered S → D (applied dominant of D-function chord) → T
    altered D → T (applied dominant of T-function chord) → S

## Example in A major (Bach chorales)
  - To emphasize E major (V), use: B7 (V7/V) → E (V)
  - The B7 chord contains D# which resolves up to E
"""

# ──────────────────────────────────────────────────────────────────────────────
# Assembled context blocks for agent system prompts.
# ──────────────────────────────────────────────────────────────────────────────

# Full theory reference — ALL six chapters.
# In the hub-and-spoke architecture, only the Theory Agent (the critic) receives
# textbook context. The Harmonizer generates from musicianship alone.
FULL_THEORY_CONTEXT = "\n\n".join([
    HARMONIC_FUNCTIONS,
    HARMONIC_SYNTAX_PHRASE,
    HARMONIC_SYNTAX_PROLONGATION,
    CADENCE_TYPES,
    ALTERED_SUBDOMINANT_CHORDS,
    APPLIED_CHORDS,
])

# Legacy split contexts (kept for reference / alternative configurations)
THEORY_AGENT_CONTEXT = "\n\n".join([
    HARMONIC_FUNCTIONS,
    HARMONIC_SYNTAX_PHRASE,
    HARMONIC_SYNTAX_PROLONGATION,
])

HARMONIZER_AGENT_CONTEXT = "\n\n".join([
    CADENCE_TYPES,
    ALTERED_SUBDOMINANT_CHORDS,
    APPLIED_CHORDS,
])
