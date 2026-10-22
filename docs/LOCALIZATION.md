# Localization and natural language

Every text a user reads in this repository (the translations in `custom_components/ztm_warsaw/translations/`, the eight READMEs, the wiki, the notices in Repairs, the changelog) has to read as if a competent native speaker had written it for that language. A translation that passes `tests/test_translations.py` is correct in its structure only: the tests do not tell whether a sentence sounds natural. This page is the standard for that, for people and for agents alike.

## The languages

English (`en`) is the source. Polish (`pl`) is for readers in Poland, German (`de`) for Germany, French (`fr`) for France, Spanish (`es`) for Spain and Italian (`it`) for Italy. Ukrainian (`uk`) and Russian (`ru`) are the standard languages. Each file keeps one regional variety, and every language gets the same care, including Polish and English.

## Write for the reader, not for the English sentence

A translation carries the meaning and the intention, not the English sentence structure. Before writing a text, find out what the integration tells the user here, what the user has to understand or do, and how a native speaker would say it in a transport app or in Home Assistant. Then write that, and reorder, split or merge sentences where the language wants it. If a wording looks suspiciously close to the English one, rewrite it.

Existing translations can be wrong. Do not copy one only because it is already in the repository; when you correct a recurring term, correct all its occurrences.

## Style of this project

- A sentence has an explicit subject: "The integration displays the next departures", not "Shows the next departures". In Polish "wyświetla", not "pokazuje", for what the integration or a sensor does.
- Natural sentences are better than telegraphic fragments, and a short text is good only when it stays easy to understand.
- Proper names are not translated. The name Home Assistant is not inflected in Polish ("w Home Assistant", "Uruchom ponownie Home Assistant").
- Use one form of address per language and keep it everywhere.
- No marketing tone, no artificial enthusiasm and no filler that only sounds like a machine's polish.
- An error text says what failed: an input of the user, the City's API being unavailable, or the configuration. It never promises what the integration does not do.

## What the words mean

The vocabulary of a public transport timetable has meanings that must not be mixed, and the English source words are not always the best guide.

| English | Meaning in this integration | Note |
|---|---|---|
| stop | a place with a name, for example "Dworzec Centralny" (the City's *zespół*) | one stop has one or more poles |
| pole | one numbered boarding place of a stop (the City's *słupek*, the number on the sign) | in a text for a passenger it is the place where a vehicle leaves in one direction; do not translate it as the literal word for a post if a language has a better transport word |
| line | a route with a number or a letter, for example 151 or N31 | |
| direction | where the line goes from the pole, read from the timetable | |
| departure | one scheduled departure from the timetable | not a live prediction |
| token | the credential of the City's new API | an old API key is a different thing (and no longer works) |

The terms in use today for *stop*, *pole* and *line* are:

| | pl | de | fr | es | it | uk | ru |
|---|---|---|---|---|---|---|---|
| stop | przystanek | Haltestelle | arrêt | parada | fermata | зупинка | остановка |
| pole | słupek | Mast | poteau | poste | palo | стовпчик | столбик |
| line | linia | Linie | ligne | línea | linea | маршрут | линия |

These are not settled. The words for *pole* are close to the Polish *słupek* and may not be what a local transport rider says, and *line* is not used the same way in the Ukrainian and Russian texts. An agent that is unsure about such a word writes the best candidate and names the question in the pull request, so that a native speaker can decide; it does not claim that a native speaker has approved the text.

## Checking a text

For every user-facing text that is added or changed:

1. Understand where it appears and what the user does there.
2. Check that the English text says what the integration does.
3. Write each language on its own, then read it again as an editor of that language: grammar, word order, register, terminology, and whether it sounds like a translation.
4. Check that placeholders (`{line}`, `{stop}`, `{portal}`), links, Markdown and paragraph breaks are intact, and that related texts use the same words.
5. Run the tests, and treat a pass as the minimum, not as proof of quality.

The keys, the placeholders, the URLs, the identifiers and the names of products stay as they are. A language never falls back to English text without a decision of the maintainer.

## In a pull request

A pull request that changes a user-facing text updates every language, says which languages changed, and lists the terminology questions that need a native speaker. A machine translation is not described as reviewed by a native speaker. The maintainer decides what is better when a reviewer and the author disagree: an automatic opinion on style is a hint, not a gate.
