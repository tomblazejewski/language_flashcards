# ADR-0005: Flexible flashcard columns via JSON

**Date:** 2026-03-28
**Status:** Accepted

## Context

A flashcard in this app can represent different kinds of study material (vocabulary, grammar, kanji, phrases, etc.). Different courses need different fields. For example:

- Vocabulary course: `Word`, `Translation`, `Pronunciation`, `Part of speech`
- Kanji course: `Kanji`, `Reading`, `Meaning`, `Stroke order image`
- Sentence course: `Sentence`, `Translation`, `Audio`

The study mode must be able to test *any* column as the question and *any* column as the answer, not just a fixed "front/back".

## Decision

- `Course.column_definitions` — `JSON` column containing an ordered array of column descriptors:
  ```json
  [
    {"name": "Word",          "type": "text"},
    {"name": "Translation",   "type": "text"},
    {"name": "Pronunciation", "type": "text"},
    {"name": "Example",       "type": "text"}
  ]
  ```
  Supported types (v1): `text`, `image_url`, `audio_url`.

- `Flashcard.data` — `JSON` column keyed by column name:
  ```json
  {
    "Word": "猫",
    "Translation": "cat",
    "Pronunciation": "māo",
    "Example": "猫が好きです"
  }
  ```

- `ReviewConfig` — links a user to a course and specifies `question_column` + `answer_column`, enabling multiple independent review directions per course.

## Rationale

- Avoids a rigid two-column (front/back) model without requiring a full EAV schema
- JSON is readable, versionable, and easy to validate with Pydantic
- PostgreSQL JSONB makes the data queryable if needed in future
- Column definitions live on the Course so all flashcards in a course share the same schema, keeping data consistent

## Alternatives considered

| Option | Reason rejected |
|---|---|
| Fixed front/back + extra fields | Cannot model multi-directional testing or rich schemas |
| EAV table (rows per column value) | Complex queries, poor performance, hard to reason about |
| Per-course dynamic SQL tables | Migration nightmare; impossible for user-created courses |

## Consequences

- Pydantic models validate that `Flashcard.data` keys match `Course.column_definitions` names at write time
- `ReviewConfig.question_column` and `answer_column` are validated against `Course.column_definitions` at creation time
- Adding a new column to a course requires a migration step: all existing flashcards get the new key with a `null` value
- Flutter renders flashcard fields dynamically based on `column_definitions`; no hard-coded field names in the UI
