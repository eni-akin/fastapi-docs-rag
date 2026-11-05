# Parser fixture sources

Captured November 5, 2026. The three small FastAPI excerpts retain the original
heading, introduction, first code tab, and first callout. Other site content was
removed to keep the tests readable. The syntax-highlighting spans are retained
so the tests verify extraction from the HTML readers actually see.

- `first-steps.html`: https://fastapi.tiangolo.com/tutorial/first-steps/
- `dependencies.html`: https://fastapi.tiangolo.com/tutorial/dependencies/
- `yield.html`: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/

These excerpts are from FastAPI, Copyright (c) 2018 Sebastián Ramírez, under the
MIT license reproduced in `FASTAPI-LICENSE.txt`.

`structure.html` is a synthetic layout fixture covering alternative tabs,
warnings, tables, nested lists, Unicode, and an anchorless section. The long-code
test generates its own oversized example; it performs no model truncation.
