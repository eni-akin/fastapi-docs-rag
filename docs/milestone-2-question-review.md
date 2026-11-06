# Milestone 2: development question review

These 20 questions and evidence labels are **unreviewed agent drafts**. Check the question,
proposed facts, answerability within the captured eight pages, and the exact evidence in
`evals/development-draft.json`. Approve or correct IDs in chat; only explicit review will be recorded.
Span/checksum validation establishes provenance; it does not establish semantic correctness.

## dev-01: How do I create a GET endpoint with FastAPI?

Proposed answerable: True. Review status: draft.

Proposed fact: Create a FastAPI application and use an app.get decorator with an async route function.

- [Source section](https://fastapi.tiangolo.com/tutorial/first-steps/#first-steps), captured block 1, characters 0–47.
- [Source section](https://fastapi.tiangolo.com/tutorial/first-steps/#first-steps), captured block 2, characters 0–117.

## dev-02: Where can I open the interactive API documentation?

Proposed answerable: True. Review status: draft.

Proposed fact: The default interactive documentation is available at /docs.

- [Source section](https://fastapi.tiangolo.com/tutorial/first-steps/#interactive-api-docs), captured block 16, characters 0–37.

## dev-03: How does FastAPI convert an int path parameter?

Proposed answerable: True. Review status: draft.

Proposed fact: An int annotation makes the path value arrive as an integer after conversion.

- [Source section](https://fastapi.tiangolo.com/tutorial/path-params/#path-parameters-with-types), captured block 8, characters 0–143.
- [Source section](https://fastapi.tiangolo.com/tutorial/path-params/#data-conversion), captured block 16, characters 0–100.
- [Source section](https://fastapi.tiangolo.com/tutorial/path-params/#data-conversion), captured block 17, characters 0–78.

## dev-04: Why should a fixed path operation appear before a parameterized route?

Proposed answerable: True. Review status: draft.

Proposed fact: Path operations are evaluated in order, so a fixed route must precede a matching parameter route.

- [Source section](https://fastapi.tiangolo.com/tutorial/path-params/#order-matters), captured block 43, characters 0–101.
- [Source section](https://fastapi.tiangolo.com/tutorial/path-params/#order-matters), captured block 44, characters 0–146.
- [Source section](https://fastapi.tiangolo.com/tutorial/path-params/#order-matters), captured block 45, characters 0–236.

## dev-05: How do I give skip and limit query parameters default values?

Proposed answerable: True. Review status: draft.

Proposed fact: Defaults in function parameters supply values when query parameters are omitted.

- [Source section](https://fastapi.tiangolo.com/tutorial/query-params/#defaults), captured block 17, characters 0–101.
- [Source section](https://fastapi.tiangolo.com/tutorial/query-params/#defaults), captured block 18, characters 0–69.
- [Source section](https://fastapi.tiangolo.com/tutorial/query-params/#defaults), captured block 26, characters 0–38.
- [Source section](https://fastapi.tiangolo.com/tutorial/query-params/#defaults), captured block 27, characters 0–44.

## dev-06: How do I make a query parameter optional?

Proposed answerable: True. Review status: draft.

Proposed fact: A None default makes the query parameter optional in the documented example.

- [Source section](https://fastapi.tiangolo.com/tutorial/query-params/#optional-parameters), captured block 29, characters 0–90.
- [Source section](https://fastapi.tiangolo.com/tutorial/query-params/#optional-parameters), captured block 30, characters 0–219.

## dev-07: Can a boolean query parameter accept values such as yes or on?

Proposed answerable: True. Review status: draft.

Proposed fact: The documented boolean conversion accepts several true-like query strings.

- [Source section](https://fastapi.tiangolo.com/tutorial/query-params/#query-parameter-type-conversion), captured block 35, characters 0–60.
- [Source section](https://fastapi.tiangolo.com/tutorial/query-params/#query-parameter-type-conversion), captured block 36, characters 0–374.
- [Source section](https://fastapi.tiangolo.com/tutorial/query-params/#query-parameter-type-conversion), captured block 44, characters 0–41.
- [Source section](https://fastapi.tiangolo.com/tutorial/query-params/#query-parameter-type-conversion), captured block 46, characters 0–42.
- [Source section](https://fastapi.tiangolo.com/tutorial/query-params/#query-parameter-type-conversion), captured block 47, characters 0–142.

## dev-08: How do I define a JSON request body with Pydantic?

Proposed answerable: True. Review status: draft.

Proposed fact: Declare a BaseModel subclass with annotated fields and use it as a route parameter.

- [Source section](https://fastapi.tiangolo.com/tutorial/body/#create-your-data-model), captured block 13, characters 0–73.
- [Source section](https://fastapi.tiangolo.com/tutorial/body/#create-your-data-model), captured block 15, characters 0–271.

## dev-09: Can one endpoint use a request body with path and query parameters?

Proposed answerable: True. Review status: draft.

Proposed fact: The documented endpoint combines path parameters, an Item body model, and optional query data.

- [Source section](https://fastapi.tiangolo.com/tutorial/body/#request-body-path-query-parameters), captured block 62, characters 0–75.
- [Source section](https://fastapi.tiangolo.com/tutorial/body/#request-body-path-query-parameters), captured block 64, characters 0–414.

## dev-10: What does response_model do to returned data?

Proposed answerable: True. Review status: draft.

Proposed fact: The declared response model validates, converts, documents, and filters the returned output.

- [Source section](https://fastapi.tiangolo.com/tutorial/response-model/#response-model-parameter), captured block 29, characters 0–159.

## dev-11: How can I avoid returning an input password in my response?

Proposed answerable: True. Review status: draft.

Proposed fact: Use a distinct output model that omits the password field.

- [Source section](https://fastapi.tiangolo.com/tutorial/response-model/#add-an-output-model), captured block 54, characters 0–96.
- [Source section](https://fastapi.tiangolo.com/tutorial/response-model/#add-an-output-model), captured block 55, characters 0–431.

## dev-12: Which takes priority when both a return annotation and response_model are declared?

Proposed answerable: True. Review status: draft.

Proposed fact: The response_model takes priority over the return type annotation.

- [Source section](https://fastapi.tiangolo.com/tutorial/response-model/#response-model-priority), captured block 34, characters 0–117.

## dev-13: How do I receive a shared dependency value in a route?

Proposed answerable: True. Review status: draft.

Proposed fact: Declare a parameter with Depends on the dependency function.

- [Source section](https://fastapi.tiangolo.com/tutorial/dependencies/#declare-the-dependency-in-the-dependant), captured block 44, characters 0–118.
- [Source section](https://fastapi.tiangolo.com/tutorial/dependencies/#declare-the-dependency-in-the-dependant), captured block 45, characters 0–454.

## dev-14: How do I reuse an Annotated dependency declaration across routes?

Proposed answerable: True. Review status: draft.

Proposed fact: Assign an Annotated dependency type to an alias and reuse it in route signatures.

- [Source section](https://fastapi.tiangolo.com/tutorial/dependencies/#share-annotated-dependencies), captured block 70, characters 0–114.
- [Source section](https://fastapi.tiangolo.com/tutorial/dependencies/#share-annotated-dependencies), captured block 71, characters 0–447.

## dev-15: How do I close a database resource in a dependency with yield?

Proposed answerable: True. Review status: draft.

Proposed fact: Yield the resource inside try and close it in finally after its use.

- [Source section](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#a-database-dependency-with-yield), captured block 12, characters 0–90.
- [Source section](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#a-database-dependency-with-yield), captured block 14, characters 0–99.

## dev-16: How can a dependency with yield translate a caught exception into HTTPException?

Proposed answerable: True. Review status: draft.

Proposed fact: Catch the exception in an except block and raise HTTPException, as in the documented dependency.

- [Source section](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#dependencies-with-yield-and-httpexception), captured block 54, characters 0–88.
- [Source section](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#dependencies-with-yield-and-httpexception), captured block 55, characters 0–69.
- [Source section](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#dependencies-with-yield-and-httpexception), captured block 59, characters 0–775.

## dev-17: How do I call FastAPI endpoints from a test without starting a live server?

Proposed answerable: True. Review status: draft.

Proposed fact: Use TestClient with the application and regular test functions.

- [Source section](https://fastapi.tiangolo.com/tutorial/testing/#using-testclient), captured block 10, characters 0–62.
- [Source section](https://fastapi.tiangolo.com/tutorial/testing/#using-testclient), captured block 11, characters 0–91.
- [Source section](https://fastapi.tiangolo.com/tutorial/testing/#using-testclient), captured block 14, characters 0–334.
- [Source section](https://fastapi.tiangolo.com/tutorial/testing/#using-testclient), captured block 16, characters 0–64.

## dev-18: How do I check a response status code and JSON body in a test?

Proposed answerable: True. Review status: draft.

Proposed fact: Call the endpoint through TestClient and assert its status_code and json result.

- [Source section](https://fastapi.tiangolo.com/tutorial/testing/#using-testclient), captured block 14, characters 0–334.

## dev-19: What producer settings guarantee exactly-once Kafka writes from a FastAPI endpoint?

Proposed answerable: False. Review status: draft.

Proposed reason: The captured eight-page tutorial subset does not document Kafka producer transactional configuration.

## dev-20: How should I configure NGINX mutual TLS certificate rotation for this application?

Proposed answerable: False. Review status: draft.

Proposed reason: This captured subset does not contain NGINX mutual TLS and certificate-rotation configuration.
