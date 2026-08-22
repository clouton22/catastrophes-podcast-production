# Catastrophes — Project Context

## Project premise

**Catastrophes** is an alternate-history project presented as an in-universe history podcast recorded in the late 2090s or around 2100.

The podcast host is a professional historian living entirely inside that history. She has no awareness that her world differs from the real listener's world.

The real audience hears a curated selection of **17 produced episodes** from a much larger fictional podcast. Gaps in the fictional episode numbering are intentional. They imply that the in-universe audience has heard many episodes that the real audience has not.

The divergence begins in 1912, when **Titanic does not sink**. It narrowly avoids an iceberg. The incident produces investigations and warnings, but because the ship survives, the dominant lesson is that the existing system worked.

In 1925, the American liner **Columbia** strikes ice and sinks, killing more than two thousand people. Investigators discover the earlier Titanic records and find that many of the weaknesses exposed by Columbia had already been identified.

This helps produce a renewed Progressive political tradition centered on systemic risk, near misses, prevention, verification, redundancy, institutional design, and the idea that individually reasonable decisions can collectively produce catastrophic outcomes.

The history eventually contains four major wars collectively called **the Catastrophes**:

1. The Great War
2. The Fascist War
3. The Coalition War
4. The World War

The World War of 2033–2042 is the fourth Catastrophe. It combines great-power escalation with ideological total war and culminates in the first wartime use of atomic weapons in this history.

---

## The two audiences

Every produced episode must work simultaneously for two different audiences.

### The in-universe listener

The fictional listener knows the complete podcast.

They have heard the unproduced episodes between the selected episodes. They know the historical terminology, important political figures, wars, institutions, and broad sequence of events.

The host always speaks naturally to this audience.

### The real listener

The real listener hears only the selected production episodes.

They gradually reconstruct how history differs through:

- dates
- changed careers of recognizable historical people
- terminology
- political institutions
- callbacks
- apparent omissions
- references to fictional episodes they have not heard
- familiar events that happen differently
- unfamiliar events treated by the host as common knowledge

The host must never explain the alternate-history conceit for the benefit of this audience.

The real listener should frequently have the experience of realizing:

> Wait. Something is different here.

Later this should evolve into:

> I recognize these people, but not their lives.

And eventually:

> This world now has a history of its own.

---

## Production episodes versus in-universe episodes

There are two separate numbering systems.

They must never be confused.

### Production episode

The **production episode** is the real listening order.

There are currently 17 planned production episodes.

Production numbering is sequential:

1, 2, 3, 4 ... 17.

Production numbers are operational metadata and should be used for:

- filenames
- source script filenames
- generated TTS chunks
- assembled audio
- post-production files
- sorting
- RSS episode numbers
- tooling
- internal production metadata

### Book and in-universe episode

The fictional complete podcast is organized into Books and Episodes.

These numbers are part of the fiction.

They should appear in:

- visible episode titles
- descriptions where useful
- the host's spoken introduction

They should generally not determine operational filenames or sorting.

### Production script header

Use:

```text
@production 5
@book 3
@episode 8
@title The Atomic Settlement