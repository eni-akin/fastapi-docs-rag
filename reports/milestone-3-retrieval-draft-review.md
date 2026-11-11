# Development question review sheet

60 of 60 records await human approval. The owner must approve or correct expected facts, answerability, source spans, grades, alternatives, and sufficiency before the milestone quality gate can pass.

## dev-01 — direct_lookup

**Question:** How do I create a GET endpoint with FastAPI?

**Proposed answerable:** True

- Fact `support`: Create a FastAPI application and use an app.get decorator with an async route function.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/first-steps/#first-steps block 2 [0:117], grade 2: 'from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get("/")\nasync def root():\n    return {"message": "Hello World"}\n'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-02 — direct_lookup

**Question:** Where can I open the interactive API documentation?

**Proposed answerable:** True

- Fact `support`: The default interactive documentation is available at /docs.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/first-steps/#interactive-api-docs block 16 [0:37], grade 2: 'Now go to http://127.0.0.1:8000/docs.'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-03 — direct_lookup

**Question:** How does FastAPI convert an int path parameter?

**Proposed answerable:** True

- Fact `support`: An int annotation makes the path value arrive as an integer after conversion.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/path-params/#data-conversion block 16 [0:100], grade 2: 'Notice that the value your function received (and returned) is 3, as a Python int, not a string "3".'
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/path-params/#data-conversion block 17 [0:78], grade 2: 'So, with that type declaration, FastAPI gives you automatic request "parsing".'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-04 — paraphrase

**Question:** Why should a fixed path operation appear before a parameterized route?

**Proposed answerable:** True

- Fact `support`: Path operations are evaluated in order, so a fixed route must precede a matching parameter route.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/path-params/#order-matters block 44 [0:146], grade 2: 'Because path operations are evaluated in order, you need to make sure that the path for /users/me is declared before the one for /users/{use'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-05 — direct_lookup

**Question:** How do I give skip and limit query parameters default values?

**Proposed answerable:** True

- Fact `support`: Defaults in function parameters supply values when query parameters are omitted.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/query-params/#defaults block 18 [0:69], grade 2: 'In the example above they have default values of skip=0 and limit=10.'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-06 — direct_lookup

**Question:** How do I make a query parameter optional?

**Proposed answerable:** True

- Fact `support`: A None default makes the query parameter optional in the documented example.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/query-params/#optional-parameters block 29 [0:90], grade 2: 'The same way, you can declare optional query parameters, by setting their default to None:'
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/query-params/#optional-parameters block 30 [0:219], grade 2: 'from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get("/items/{item_id}")\nasync def read_item(item_id: str, q: str | None = None):\n    if '

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-07 — direct_lookup

**Question:** Can a boolean query parameter accept values such as yes or on?

**Proposed answerable:** True

- Fact `support`: The documented boolean conversion accepts several true-like query strings.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/query-params/#query-parameter-type-conversion block 44 [0:41], grade 2: 'http://127.0.0.1:8000/items/foo?short=on\n'
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/query-params/#query-parameter-type-conversion block 46 [0:42], grade 2: 'http://127.0.0.1:8000/items/foo?short=yes\n'
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/query-params/#query-parameter-type-conversion block 47 [0:142], grade 2: 'or any other case variation (uppercase, first letter in uppercase, etc), your function will see the parameter short with a bool value of Tru'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-08 — direct_lookup

**Question:** How do I define a JSON request body with Pydantic?

**Proposed answerable:** True

- Fact `support`: Declare a BaseModel subclass with annotated fields and use it as a route parameter.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/body/#create-your-data-model block 13 [0:73], grade 2: 'Then you declare your data model as a class that inherits from BaseModel.'
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/body/#create-your-data-model block 15 [0:271], grade 2: 'from fastapi import FastAPI\nfrom pydantic import BaseModel\n\n\nclass Item(BaseModel):\n    name: str\n    description: str | None = None\n    pri'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-09 — direct_lookup

**Question:** Can one endpoint use a request body with path and query parameters?

**Proposed answerable:** True

- Fact `support`: The documented endpoint combines path parameters, an Item body model, and optional query data.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/body/#request-body-path-query-parameters block 62 [0:75], grade 2: 'You can also declare body, path and query parameters, all at the same time.'
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/body/#request-body-path-query-parameters block 64 [0:414], grade 2: 'from fastapi import FastAPI\nfrom pydantic import BaseModel\n\n\nclass Item(BaseModel):\n    name: str\n    description: str | None = None\n    pri'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-10 — direct_lookup

**Question:** What does response_model do to returned data?

**Proposed answerable:** True

- Fact `support`: The declared response model validates, converts, documents, and filters the returned output.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/response-model/#response-model-parameter block 29 [0:159], grade 2: 'FastAPI will use this response_model to do all the data documentation, validation, etc. and also to convert and filter the output data to it'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-11 — paraphrase

**Question:** How can I avoid returning an input password in my response?

**Proposed answerable:** True

- Fact `support`: Use a distinct output model that omits the password field.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/response-model/#add-an-output-model block 54 [0:96], grade 2: 'We can instead create an input model with the plaintext password and an output model without it:'
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/response-model/#add-an-output-model block 55 [0:431], grade 2: 'from typing import Any\n\nfrom fastapi import FastAPI\nfrom pydantic import BaseModel, EmailStr\n\napp = FastAPI()\n\n\nclass UserIn(BaseModel):\n   '

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-12 — direct_lookup

**Question:** Which takes priority when both a return annotation and response_model are declared?

**Proposed answerable:** True

- Fact `support`: The response_model takes priority over the return type annotation.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/response-model/#response-model-priority block 34 [0:117], grade 2: 'If you declare both a return type and a response_model, the response_model will take priority and be used by FastAPI.'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-13 — paraphrase

**Question:** How do I receive a shared dependency value in a route?

**Proposed answerable:** True

- Fact `support`: Declare a parameter with Depends on the dependency function.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/dependencies/#declare-the-dependency-in-the-dependant block 44 [0:118], grade 2: 'The same way you use Body, Query, etc. with your path operation function parameters, use Depends with a new parameter:'
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/dependencies/#declare-the-dependency-in-the-dependant block 45 [0:454], grade 2: 'from typing import Annotated\n\nfrom fastapi import Depends, FastAPI\n\napp = FastAPI()\n\n\nasync def common_parameters(q: str | None = None, skip'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-14 — direct_lookup

**Question:** How do I reuse an Annotated dependency declaration across routes?

**Proposed answerable:** True

- Fact `support`: Assign an Annotated dependency type to an alias and reuse it in route signatures.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/dependencies/#share-annotated-dependencies block 70 [0:114], grade 2: 'But because we are using Annotated, we can store that Annotated value in a variable and use it in multiple places:'
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/dependencies/#share-annotated-dependencies block 71 [0:447], grade 2: 'from typing import Annotated\n\nfrom fastapi import Depends, FastAPI\n\napp = FastAPI()\n\n\nasync def common_parameters(q: str | None = None, skip'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-15 — paraphrase

**Question:** How do I close a database resource in a dependency with yield?

**Proposed answerable:** True

- Fact `support`: Yield the resource inside try and close it in finally after its use.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#a-database-dependency-with-yield block 14 [0:99], grade 2: 'async def get_db():\n    db = DBSession()\n    try:\n        yield db\n    finally:\n        db.close()\n'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-16 — paraphrase

**Question:** How can a dependency with yield translate a caught exception into HTTPException?

**Proposed answerable:** True

- Fact `support`: Catch the exception in an except block and raise HTTPException, as in the documented dependency.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#dependencies-with-yield-and-httpexception block 59 [0:775], grade 2: 'from typing import Annotated\n\nfrom fastapi import Depends, FastAPI, HTTPException\n\napp = FastAPI()\n\n\ndata = {\n    "plumbus": {"description":'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-17 — direct_lookup

**Question:** How do I call FastAPI endpoints from a test without starting a live server?

**Proposed answerable:** True

- Fact `support`: Use TestClient with the application and regular test functions.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/testing/#using-testclient block 10 [0:62], grade 2: 'Create a TestClient by passing your FastAPI application to it.'
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/testing/#using-testclient block 14 [0:334], grade 2: 'from fastapi import FastAPI\nfrom fastapi.testclient import TestClient\n\napp = FastAPI()\n\n\n@app.get("/")\nasync def read_main():\n    return {"m'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-18 — direct_lookup

**Question:** How do I check a response status code and JSON body in a test?

**Proposed answerable:** True

- Fact `support`: Call the endpoint through TestClient and assert its status_code and json result.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/testing/#using-testclient block 14 [0:334], grade 2: 'from fastapi import FastAPI\nfrom fastapi.testclient import TestClient\n\napp = FastAPI()\n\n\n@app.get("/")\nasync def read_main():\n    return {"m'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-19 — unsupported

**Question:** What producer settings guarantee exactly-once Kafka writes from a FastAPI endpoint?

**Proposed answerable:** False

- Proposed reason: The captured 14-page tutorial subset does not document Kafka producer transactional configuration.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-20 — unsupported

**Question:** How should I configure NGINX mutual TLS certificate rotation for this application?

**Proposed answerable:** False

- Proposed reason: This captured 14-page subset does not contain NGINX mutual TLS and certificate-rotation configuration.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-21 — direct_lookup

**Question:** Where should Field be imported from for a Pydantic model attribute?

**Proposed answerable:** True

- Fact `fact-1`: Import Field from pydantic.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/body-fields/#import-field block 14 [12:52], grade 2: 'Field is imported directly from pydantic'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-22 — direct_lookup

**Question:** What does Header do with underscores in Python parameter names?

**Proposed answerable:** True

- Fact `fact-1`: Header converts underscores to hyphens by default.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/header-params/#automatic-conversion block 30 [16:100], grade 2: 'Header will convert the parameter names characters from underscore (_) to hyphen (-)'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-23 — multi_section

**Question:** How do I declare a response status code and check the returned status in a test?

**Proposed answerable:** True

- Fact `fact-1`: Declare status_code on the path-operation decorator.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/response-status-code/#response-status-code block 13 [12:64], grade 2: 'status_code is a parameter of the "decorator" method'
- Fact `fact-2`: Use a TestClient response assertion to check the status code.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/testing/#using-testclient block 14 [246:280], grade 2: 'assert response.status_code == 200'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-24 — paraphrase

**Question:** How can I cap the length of an optional search string?

**Proposed answerable:** True

- Fact `fact-1`: Use Query(max_length=50) inside Annotated.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#add-query-to-annotated-in-the-q-parameter block 44 [16:56], grade 2: 'Query(max_length=50) inside of Annotated'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-25 — paraphrase

**Question:** Can a URL supply q more than once and preserve both values?

**Proposed answerable:** True

- Fact `fact-1`: A list query parameter declared with Query receives repeated values.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#query-parameter-list-multiple-values block 148 [10:88], grade 2: "receive the multiple q query parameters' values (foo and bar) in a Python list"

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-26 — paraphrase

**Question:** How can a hyphenated public query name map to a Python variable?

**Proposed answerable:** True

- Fact `fact-1`: Declare a Query alias.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#alias-parameters block 200 [0:94], grade 2: 'Then you can declare an alias, and that alias is what will be used to find the parameter value'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-27 — paraphrase

**Question:** How do I add extra JSON Schema metadata to a model field?

**Proposed answerable:** True

- Fact `fact-1`: Pass json_schema_extra to Field.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/body-fields/#add-extra-information block 31 [0:65], grade 2: 'You can declare extra information with json_schema_extra in Field'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-28 — paraphrase

**Question:** Should an endpoint return or raise HTTPException?

**Proposed answerable:** True

- Fact `fact-1`: Raise HTTPException as a Python exception.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/handling-errors/#raise-an-httpexception-in-your-code block 22 [33:66], grade 2: "you don't return it, you raise it"

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-29 — paraphrase

**Question:** Can HTTPException detail contain a JSON object instead of text?

**Proposed answerable:** True

- Fact `fact-1`: The detail can be any JSON-convertible value.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/handling-errors/#the-resulting-response block 33 [31:107], grade 2: 'you can pass any value that can be converted to JSON as the parameter detail'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-30 — paraphrase

**Question:** Which exception signals invalid request data inside FastAPI?

**Proposed answerable:** True

- Fact `fact-1`: FastAPI raises RequestValidationError.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/handling-errors/#override-request-validation-exceptions block 59 [38:88], grade 2: 'FastAPI internally raises a RequestValidationError'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-31 — paraphrase

**Question:** Must a dependency be a function?

**Proposed answerable:** True

- Fact `fact-1`: A dependency can be any callable, including a class.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/dependencies/classes-as-dependencies/#what-makes-a-dependency block 19 [23:58], grade 2: 'a dependency should be a "callable"'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-32 — paraphrase

**Question:** What shorthand avoids naming a dependency class twice?

**Proposed answerable:** True

- Fact `fact-1`: Use the class as the type and Depends() without an argument.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/dependencies/classes-as-dependencies/#shortcut block 115 [65:100], grade 2: 'use Depends() without any parameter'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-33 — paraphrase

**Question:** How can an endpoint collect repeated X-Token header values?

**Proposed answerable:** True

- Fact `fact-1`: Declare the header parameter as a list.
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/header-params/#duplicate-headers block 43 [0:63], grade 2: 'You can define those cases using a list in the type declaration'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-34 — multi_section

**Question:** When is q optional, and how can I make it required while still using Query?

**Proposed answerable:** True

- Fact `fact-1`: A default value makes q optional
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#default-values block 113 [0:80], grade 2: 'Having a default value of any type, including None, makes the parameter optional'
- Fact `fact-2`: Omitting the default makes q required
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#required-parameters block 121 [68:110], grade 2: 'you can simply not declare a default value'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-35 — multi_section

**Question:** How do I impose both a maximum and a minimum string length on q?

**Proposed answerable:** True

- Fact `fact-1`: Query supports max_length
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#add-query-to-annotated-in-the-q-parameter block 44 [16:56], grade 2: 'Query(max_length=50) inside of Annotated'
- Fact `fact-2`: Query also supports min_length
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#add-more-validations block 85 [0:39], grade 2: 'You can also add a parameter min_length'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-36 — multi_section

**Question:** How can a model field validate input and add extra schema metadata?

**Proposed answerable:** True

- Fact `fact-1`: Field declares validation and metadata
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/body-fields/#recap block 36 [8:70], grade 2: "use Pydantic's Field to declare extra validations and metadata"
- Fact `fact-2`: json_schema_extra adds schema information
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/body-fields/#add-extra-information block 31 [0:65], grade 2: 'You can declare extra information with json_schema_extra in Field'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-37 — multi_section

**Question:** How are Python header names mapped to HTTP names, and how are duplicates collected?

**Proposed answerable:** True

- Fact `fact-1`: Header maps underscores to hyphens
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/header-params/#automatic-conversion block 30 [16:100], grade 2: 'Header will convert the parameter names characters from underscore (_) to hyphen (-)'
- Fact `fact-2`: A list type collects duplicate headers
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/header-params/#duplicate-headers block 43 [0:63], grade 2: 'You can define those cases using a list in the type declaration'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-38 — multi_section

**Question:** Which documented statuses mean Created and No Content?

**Proposed answerable:** True

- Fact `fact-1`: 201 means Created
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/response-status-code/#about-http-status-codes block 32 [25:39], grade 2: '201, "Created"'
- Fact `fact-2`: 204 means No Content and has no body
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/response-status-code/#about-http-status-codes block 33 [18:35], grade 2: '204, "No Content"'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-39 — multi_section

**Question:** How does an endpoint report a missing item and attach an error header?

**Proposed answerable:** True

- Fact `fact-1`: Raise HTTPException with 404 for a missing item
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/handling-errors/#raise-an-httpexception-in-your-code block 25 [79:123], grade 2: 'raise an exception with a status code of 404'
- Fact `fact-2`: HTTPException can carry custom error headers
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/handling-errors/#add-custom-headers block 37 [58:94], grade 2: 'add custom headers to the HTTP error'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-40 — multi_section

**Question:** How do I handle my own exception type and override validation errors?

**Proposed answerable:** True

- Fact `fact-1`: Register a custom exception handler
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/handling-errors/#install-custom-exception-handlers block 45 [46:70], grade 2: '@app.exception_handler()'
- Fact `fact-2`: Register a RequestValidationError handler
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/handling-errors/#override-request-validation-exceptions block 61 [66:112], grade 2: '@app.exception_handler(RequestValidationError)'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-41 — multi_section

**Question:** Why can CommonQueryParams be a dependency, and how are its constructor values populated?

**Proposed answerable:** True

- Fact `fact-1`: Classes are callable dependencies
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/dependencies/classes-as-dependencies/#classes-as-dependencies_1 block 32 [4:37], grade 2: 'a Python class is also a callable'
- Fact `fact-2`: FastAPI solves constructor parameters
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/dependencies/classes-as-dependencies/#classes-as-dependencies_1 block 55 [0:68], grade 2: 'Those parameters are what FastAPI will use to "solve" the dependency'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-42 — multi_section

**Question:** Can I use a class for parameter injection and a yield dependency for cleanup?

**Proposed answerable:** True

- Fact `fact-1`: Classes can be dependencies
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/dependencies/classes-as-dependencies/#classes-as-dependencies_1 block 33 [18:62], grade 2: 'you could use a Python class as a dependency'
- Fact `fact-2`: Yield dependencies run exit steps
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/#dependencies-with-yield block 2 [12:79], grade 2: 'use yield instead of return, and write the extra steps (code) after'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-43 — multi_section

**Question:** How can a request model define its shape and validate a specific field?

**Proposed answerable:** True

- Fact `fact-1`: A request model inherits BaseModel
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/body/#create-your-data-model block 13 [9:72], grade 2: 'declare your data model as a class that inherits from BaseModel'
- Fact `fact-2`: Field declares attribute validation
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/body-fields/#recap block 36 [8:70], grade 2: "use Pydantic's Field to declare extra validations and metadata"

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-44 — multi_section

**Question:** How do I filter response fields and declare a Created status?

**Proposed answerable:** True

- Fact `fact-1`: The response model filters returned data
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/response-model/#response-model-return-type block 12 [8:78], grade 2: 'limit and filter the output data to what is defined in the return type'
- Fact `fact-2`: The decorator status_code sets the status
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/response-status-code/#response-status-code block 13 [12:64], grade 2: 'status_code is a parameter of the "decorator" method'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-45 — multi_section

**Question:** How can I make a test client and have the endpoint signal a missing item?

**Proposed answerable:** True

- Fact `fact-1`: TestClient takes the FastAPI application
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/testing/#using-testclient block 10 [0:61], grade 2: 'Create a TestClient by passing your FastAPI application to it'
- Fact `fact-2`: Raise HTTPException with 404 for an absent item
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/handling-errors/#raise-an-httpexception-in-your-code block 25 [79:123], grade 2: 'raise an exception with a status code of 404'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-46 — multi_section

**Question:** How do public hyphenated query names and Python header names map to incoming requests?

**Proposed answerable:** True

- Fact `fact-1`: Query alias maps a public name
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/query-params-str-validations/#alias-parameters block 200 [13:94], grade 2: 'declare an alias, and that alias is what will be used to find the parameter value'
- Fact `fact-2`: Header converts underscores to hyphens
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/header-params/#automatic-conversion block 30 [16:100], grade 2: 'Header will convert the parameter names characters from underscore (_) to hyphen (-)'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-47 — multi_section

**Question:** How can I avoid exposing an input password in successful output and signal a missing item?

**Proposed answerable:** True

- Fact `fact-1`: Use a response model to filter output
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/response-model/#response-model-return-type block 12 [8:78], grade 2: 'limit and filter the output data to what is defined in the return type'
- Fact `fact-2`: Raise HTTPException for a missing item
  - Alternative 1: https://fastapi.tiangolo.com/tutorial/handling-errors/#raise-an-httpexception-in-your-code block 25 [79:123], grade 2: 'raise an exception with a status code of 404'

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-48 — unsupported

**Question:** What Kafka producer idempotence and transaction settings guarantee exactly-once writes?

**Proposed answerable:** False

- Proposed reason: Proposed outside the captured 14-page English Tutorial corpus; requires human review.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-49 — unsupported

**Question:** How should NGINX mutual TLS certificates be rotated without downtime?

**Proposed answerable:** False

- Proposed reason: Proposed outside the captured 14-page English Tutorial corpus; requires human review.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-50 — unsupported

**Question:** How do I set up Redis Cluster failover for FastAPI sessions?

**Proposed answerable:** False

- Proposed reason: Proposed outside the captured 14-page English Tutorial corpus; requires human review.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-51 — unsupported

**Question:** What Kubernetes HPA metrics should scale this API under traffic spikes?

**Proposed answerable:** False

- Proposed reason: Proposed outside the captured 14-page English Tutorial corpus; requires human review.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-52 — unsupported

**Question:** Which IAM policy should I attach for S3 multipart uploads?

**Proposed answerable:** False

- Proposed reason: Proposed outside the captured 14-page English Tutorial corpus; requires human review.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-53 — unsupported

**Question:** How do I expose this FastAPI route as a gRPC bidirectional stream?

**Proposed answerable:** False

- Proposed reason: Proposed outside the captured 14-page English Tutorial corpus; requires human review.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-54 — unsupported

**Question:** What Celery broker retry settings should I use for delayed jobs?

**Proposed answerable:** False

- Proposed reason: Proposed outside the captured 14-page English Tutorial corpus; requires human review.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-55 — unsupported

**Question:** How should SQLAlchemy pool_size and max_overflow be tuned for production?

**Proposed answerable:** False

- Proposed reason: Proposed outside the captured 14-page English Tutorial corpus; requires human review.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-56 — unsupported

**Question:** How do I reconnect and replay missed WebSocket messages after a server restart?

**Proposed answerable:** False

- Proposed reason: Proposed outside the captured 14-page English Tutorial corpus; requires human review.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-57 — unsupported

**Question:** How should Stripe webhook signatures and duplicate payments be handled?

**Proposed answerable:** False

- Proposed reason: Proposed outside the captured 14-page English Tutorial corpus; requires human review.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-58 — unsupported

**Question:** Which OpenTelemetry collector sampling policy meets a fixed cost budget?

**Proposed answerable:** False

- Proposed reason: Proposed outside the captured 14-page English Tutorial corpus; requires human review.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-59 — unsupported

**Question:** How do I rotate HashiCorp Vault database credentials every hour?

**Proposed answerable:** False

- Proposed reason: Proposed outside the captured 14-page English Tutorial corpus; requires human review.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______

## dev-60 — unsupported

**Question:** Which Terraform resources deploy this API to Azure Container Apps?

**Proposed answerable:** False

- Proposed reason: Proposed outside the captured 14-page English Tutorial corpus; requires human review.

Review: [ ] approve  [ ] correct  [ ] mark unsupported; Reviewer: ______; Date: ______
