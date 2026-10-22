# Localization and natural language

Every text a user reads in this repository (the translations in `custom_components/ztm_warsaw/translations/`, the eight READMEs, the wiki, the notices in Repairs, the changelog) has to read as if a competent native speaker had written it for that language. A translation that passes `tests/test_translations.py` is correct in its structure only: the tests do not tell whether a sentence sounds natural. This page is the standard for that, for people and for agents alike. It states principles, not formulas: the goal is idiomatic, professional writing, not the same sentence shape in every language.

## The languages

English (`en`) is the source. Polish (`pl`) is for readers in Poland, German (`de`) for Germany, French (`fr`) for France, Spanish (`es`) for Spain and Italian (`it`) for Italy. Ukrainian (`uk`) and Russian (`ru`) are the standard languages. Each file keeps one regional variety, and every language gets the same care, including Polish and English.

## Write for the reader, not for the English sentence

The English text defines what is meant, not how the sentence is built. Each language follows its own conventions: word order, the way it addresses a reader, whether it names the subject or leaves it out, how long a natural sentence is, which words a native speaker expects in a transport app or in Home Assistant. Those conventions can differ a lot from English and from Polish, so a translation may reorder, split or merge sentences, and may drop or add a subject where the language wants it. If a wording looks suspiciously close to the English one, rewrite it.

Existing translations can be wrong. Do not copy one only because it is already in the repository; when you correct a recurring term, correct all its occurrences.

## Style

- Prefer clear, complete sentences over telegraphic fragments. A short text is good only while it stays easy to understand.
- For what the integration or a sensor presents on the screen, the Polish "wyświetla" is usually the better verb, but "pokazuje" is not an error: choose by the sentence.
- Proper names are not translated. The maintainer does not inflect the name Home Assistant in Polish ("w Home Assistant", "Uruchom ponownie Home Assistant").
- Use one form of address per language and keep it everywhere.
- No marketing tone, no artificial enthusiasm and no filler.
- An error text says what failed: an input of the user, the City's API being unavailable, or the configuration. It never promises what the integration does not do.

## What the transport words mean

The vocabulary of a public transport timetable has meanings that must not be mixed. Describe the concept, then find how a native speaker says it; the closest English word is not the guide.

| Concept | What it is in this integration |
|---|---|
| stop | a place with a name, for example "Dworzec Centralny" (the City's *zespół*); it has one or more boarding places |
| boarding place (the City's *słupek*, called "pole" in the code) | one numbered place of a stop where vehicles leave in one direction; its number is on the sign. For a passenger it is "the place to wait for the vehicle going that way", not a post |
| line | a route with a number or a letter, for example 151 or N31 |
| direction | where the line goes from the boarding place, read from the timetable |
| departure | one scheduled departure from the timetable, not a live prediction |
| token | the credential of the City's new API; an old API key is a different thing and no longer works |

### Terminology

Verified terms (confirmed by a native speaker or by the usage of the local transport operator, with the source): none yet. Add a row only when a term is verified.

The words in the existing texts for the boarding place and for *line* were written without that check. They are open questions, not recommendations: do not copy them forward as the preferred wording. Where one is unclear, describe the concept in the language's own transport terms, write the best candidate, and name the question in the pull request.

## Checking a text

For every user-facing text that is added or changed:

1. Understand where it appears and what the user does there.
2. Check that the English text says what the integration does.
3. Write each language on its own, then read it again as an editor of that language: grammar, word order, register, terminology, and whether it sounds like a translation.
4. When a wording is ambiguous or the term is open, compare a few plausible alternatives in the actual place on the screen and choose the clearest. This is a more careful edit, not three variants of every button.
5. Check that placeholders (`{line}`, `{stop}`, `{portal}`), links, Markdown and paragraph breaks are intact, and that related texts use the same words.
6. Run the tests, and treat a pass as the minimum, not as proof of quality.

The keys, the placeholders, the URLs, the identifiers and the names of products stay as they are. A language never falls back to English text without a decision of the maintainer.

## Who has checked a text

A text is in one of three states, and the pull request says which: verified by a native speaker, written and self-reviewed by an AI, or not reviewed. An agent does not call a text natural, or approved by a native speaker, when it cannot judge that reliably or when nobody checked it; it says that the text is self-reviewed and what it is unsure about.

## In a pull request

A pull request that changes a user-facing text updates every language, says which languages changed, which state each text is in, and lists the terminology questions that need a native speaker. The maintainer decides what is better when a reviewer and the author disagree: an automatic opinion on style is a hint, not a gate.
