# Issue Tracker

This repo uses **GitHub Issues** on `tomblazejewski/language_flashcards`.

## CLI

Use the `gh` CLI for all issue operations:

- Create: `gh issue create --repo tomblazejewski/language_flashcards ...`
- List: `gh issue list --repo tomblazejewski/language_flashcards`
- View: `gh issue view <number> --repo tomblazejewski/language_flashcards`
- Comment: `gh issue comment <number> --repo tomblazejewski/language_flashcards --body-file <file>`
- Close: `gh issue close <number> --repo tomblazejewski/language_flashcards`
- Edit labels: `gh issue edit <number> --repo tomblazejewski/language_flashcards --add-label <label> --remove-label <label>`

## Notes

- Always write issue bodies to a temp file before passing to `gh` to avoid shell-escaping issues with multiline Markdown.
- The repo identifier is `tomblazejewski/language_flashcards`.
