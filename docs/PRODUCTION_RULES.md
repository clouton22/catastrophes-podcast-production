# Catastrophes — Production Rules

Standing writing, continuity, TTS, audio-production, and publication rules for **Catastrophes**. These rules are intended to be shared by ChatGPT, Codex, and local production tooling.

## 1. In-universe integrity

- The host lives entirely inside the fictional history and has no awareness of an alternate history.
- Never compare her history with the real listener's history.
- Differences must be inferred through dates, events, terminology, careers, institutions, omissions, and callbacks.
- The host may compare contemporary perceptions with later interpretations **within her own history**.
- **Never use the word `timeline` in narration.** Prefer history, period, era, chronology, sequence, development, course of events, or simply state what happened.

## 2. Two audiences

**In-universe listener:** has heard the complete fictional podcast, including unproduced episodes. The host always speaks naturally to this audience.

**Real listener:** hears only the selected production episodes. Supply needed context through ordinary recaps that sound like reminders to the fictional audience. Allow the real listener room to infer, wonder, and notice.

## 3. Numbering

There are two distinct numbering systems.

- **Production episode:** real listening order 1–17. Use for filenames, tooling, generated/assembled audio, sorting, post-production files, RSS episode number, and operational metadata.
- **Book / in-universe episode:** fictional numbering. Use in visible titles, spoken idents, and fictional references.

Production-script header:

    @production 5
    @book 3
    @episode 8
    @title The Atomic Settlement

Code should prefer explicit names such as `production_episode`, `book_number`, and `in_universe_episode`.

## 4. RSS numbering

The RSS feed serves the real listener.

- RSS season = **1**
- RSS episode = production episode 1–17
- visible title carries fictional numbering in words

Example: Production Episode 5 is RSS Season 1 / Episode 5, titled **Book Three, Episode Eight: The Atomic Settlement**. Fictional Books are not RSS seasons.

## 5. Spoken ident

The host uses only fictional numbering:

> This is Catastrophes. Book Three, Episode Eight: The Atomic Settlement.

The host never refers to production numbering. The show title works best embedded in normal speech rather than isolated as a promotional sting. Victoria particularly benefits from a preceding/following sentence that gives `Catastrophes` a natural downward cadence.

## 6. Narrator voice

Professional historian; dry, controlled, skeptical, occasionally funny, attentive to evidence, records, institutional incentives, and the difference between what people knew then and what later generations believed.

Prefer historian narration over novelistic dialogue. Brief quotations/exchanges can work when treated as evidence. Qualify famous or elegant quotations when exact documentation is uncertain.

## 7. Clean endings and repetition

- **Look for clean endings to ideas.** Once the point lands, stop. Do not over-explain merely to ensure both audiences understand.
- Repetition can create rhythm, but generally keep a repeated phrase or structure to **three repetitions or fewer** unless strongly justified.
- Let unresolved lines create productive guessing for the real listener.

## 8. Motifs must evolve

Callbacks should develop motifs rather than merely repeat them.

- **Nothing happened:** no problem → prevention worked → success became invisible → finale: nothing happening was the achievement.
- **Accounting/counting:** passenger/casualty records → accountability → atomic material control → later danger of numbers obscuring systems.
- **Trust:** unreliable → unnecessary when verification works → pure distrust becomes destabilizing → testable trust.
- **Preparedness:** prudence → doctrine → possible provocation/overextension.
- **Systemic risk:** insight → governing philosophy → dogma → rediscovered insight.
- **Near misses:** Titanic → safety culture → Second Shanghai Crisis.
- **Redundancy:** apparent waste → resilience → doctrine → institutional excess.
- **Irreversibility:** preserve the possibility of another decision; Margaret's `What is the last decision?` principle.

## 9. Light joke to serious callback

A dry aside can introduce a mundane concept that later returns in a serious register. Example: Thomas Ward, the accountant, jokes around international accounting; later Morozov says the dismantlement photograph `represented accounting.` Do not announce the callback. Use this device sparingly, roughly once per episode at most.

## 10. Real historical figures

Recognizable real people may have altered careers. The host treats those careers as ordinary and never explains what they might have done elsewhere. Use plausible immediate recognition, delayed recognition, negative-space recognition, career inversion, historical demotion, and promotion. Do not use real people merely as cameos or jokes.

## 11. Ward-family reveal

Before the Margaret Ward episode, gradually build the host's suspicious familiarity with Ward family papers and details. The eventual reveal that Margaret is the host's great-great-grandmother should retroactively explain those moments rather than arrive without setup.

## 12. Default produced-episode structure

Use this as a rhythm, not an unbreakable formula:

1. Open with callbacks to the previous produced episode and relevant intervening fictional episodes; re-establish the larger story.
2. Build rising action from unresolved developments.
3. Reach a moment of tension, breakthrough, reversal, decision, failure, or conceptual change.
4. Show consequences and falling action.
5. End by naturally setting up the **direct next fictional episode**, while leaving subtler threads a later produced selection can pick up.

Later major episodes may deliberately break this rhythm once the audience has learned it.

## 13. Cliffhangers and selection gaps

The host always behaves as though the full fictional series exists and is heard in order.

- Never write a cliffhanger aimed only at the next real production episode.
- It is fine to tease unproduced fictional episodes.
- When a later produced episode resumes a thread after a gap, recap only what the real listener needs, phrased as a reminder to the fictional listener.
- Never explain why particular episodes were selected. The production selection is invisible to the host.

## 14. TTS defaults

Current default:

- Provider: ElevenLabs
- Voice: Victoria
- Model: Eleven v3
- Use a **fixed seed across chunks**; testing showed this dramatically improves tonal continuity.

Flash 2.5 remains useful for testing or cost-sensitive work, but v3 is the preferred full-episode production model.

## 15. Chunking

- Eleven v3 hard request ceiling: 5,000 characters.
- Preferred chunk size: roughly 3,500–4,500 characters.
- Store the episode as one annotated production script and use `@chunk` markers for API requests.
- End chunks at natural conceptual/paragraph boundaries; do not maximize character count at the expense of a clean ending.

## 16. TTS prose formatting

Prefer long paragraphs, ordinary periods, and natural sentence flow. Minimize blank lines, double spaces, dramatic punctuation, and isolated fragments. Strip Markdown emphasis from narration input; stray asterisks have produced unwanted sounds. Spell dates/numbers when doing so gives more reliable pronunciation.

## 17. Chunk transitions

Slight tonal changes between chunks are acceptable if they resemble ordinary podcast pickups or edits. Do not optimize for synthetic perfection. If a transition is distracting: regenerate with the same seed, consider moving the boundary, consider a short overlap/run-up, or repair manually in Audacity.

## 18. Audio assembly

Normal workflow:

1. generate TTS chunks;
2. assemble programmatically with FFmpeg;
3. preserve a lossless WAV editing master;
4. create the distribution MP3;
5. listen through;
6. regenerate only problem chunks;
7. reassemble;
8. use Audacity for exceptional/manual fixes.

Audacity is exception handling, not the primary assembly line.

## 19. Post-production notes and provenance

Each assembled episode should record, when available: production/book/in-universe numbers, title, source script, generation time, provider, model, voice ID, seed, character counts, estimated cost, source/audio hashes, request IDs, WAV/MP3 hashes, and exact chunk start/end timestamps for Audacity repair.

Record manual edits and source/license details for Foley, music, artwork, quotations, and other incorporated material.

## 20. Background Foley

Use subtle, sparse sounds such as mouse clicks, keyboard taps, chair creaks, paper movement, or a mug set-down. They can be especially useful near edit boundaries because they make tiny voice-position changes feel natural. The desired impression is `the host moved`, not `a sound effect played`.

Do not place effects unconstrained at random. Avoid emotionally inappropriate moments. Prefer pauses, topic changes, note-checking moments, and edit boundaries. Record source and license; prefer simple publication-safe licensing such as CC0 when available.

## 21. Audio masters and loudness

Preserve a lossless WAV editing master and create the MP3 only as the distribution/listening copy. Avoid repeated lossy re-encoding. Use podcast-appropriate loudness normalization consistently.

## 22. Podcast publication

The public RSS feed uses production numbering structurally and fictional numbering visibly. Filenames/enclosure URLs prefer production numbers. Stable GUIDs must survive hosting migrations. GitHub Pages is acceptable for experimental/modest-scale hosting; production state and tooling may remain outside the public podcast repository.

## 23. Canon management

Treat established project material as canon unless deliberately revising it. If a new idea conflicts with existing canon, identify the conflict, decide explicitly which version prevails, and update the appropriate context documents. Do not silently rewrite established history.
