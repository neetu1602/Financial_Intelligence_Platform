# Interview Prep: Financial Intelligence Platform

Every "Check your understanding" question from the build, with a model interview answer.
Structure each answer as **what it is → why it matters → how it works → trade-off/alternative**.

---

## Phase 0: Project Setup & First Endpoint

### Q1. What problem does a virtual environment solve?

**Model answer:**
A virtual environment isolates a project's dependencies from every other project and from the system Python. Without it, all projects share one `site-packages`. If project A needs FastAPI 0.100 and project B needs 0.115, installing one breaks the other.

Under the hood, a venv is a directory with its own Python interpreter link and its own `site-packages`. Activating it prepends the venv's `bin/` to `PATH`, so `python`, `pip` and CLI tools like `fastapi` resolve to the venv's copies.

It also makes environments reproducible: pinned versions in `requirements.txt` (or a lockfile) let a teammate or CI rebuild the exact same environment.

**Trade-offs / alternatives:** `uv` (fast, and no activation needed with `uv run`), Poetry (dependency resolution plus lockfile), conda (data science, handles non-Python libraries). In production, Docker provides isolation at the OS level, so the venv matters less inside a container.

**Real-world example from this project:** a new terminal picked up a global `fastapi` because the venv wasn't active. The traceback path (`/Library/Frameworks/...`) revealed it.

---

### Q2. What's the difference between FastAPI and Uvicorn?

**Model answer:**
FastAPI is a web **framework**. It gives you routing, request validation via Pydantic, dependency injection and auto-generated OpenAPI docs. It defines _what_ your application does.

Uvicorn is an **ASGI server**. It opens the network socket, accepts connections, parses raw HTTP, runs the async event loop and calls the FastAPI app for each request. It defines _how_ requests reach your code.

They talk through **ASGI** (Asynchronous Server Gateway Interface), a standard contract. Any ASGI server (Uvicorn, Hypercorn, Granian) can run any ASGI app (FastAPI, Starlette, Django async).

**Production follow-up:** in production you run several Uvicorn worker processes, for example `uvicorn --workers 4` or Gunicorn managing Uvicorn workers, usually behind a reverse proxy or load balancer such as Nginx or AWS ALB.

**Analogy:** the older sync world is WSGI, for example Flask (framework) running on Gunicorn (server).

---

### Q3. Why does a production service need a `/health` endpoint?

**Model answer:**
It lets automated infrastructure check whether an instance is alive and able to serve traffic, without a human involved.

- **Load balancers** poll it and only route traffic to healthy instances.
- **Orchestrators** (Docker, Kubernetes, ECS) restart a container when it fails repeatedly.
- **Monitoring and uptime tools** alert the on-call engineer.

**Go deeper (a strong senior signal):** distinguish two kinds of check.

- **Liveness:** "is the process running?" It should be cheap and never depend on the database. If it fails, the service gets restarted.
- **Readiness:** "can I serve requests right now?" It checks dependencies like the DB connection. If it fails, the instance is taken out of rotation but _not_ restarted.

Health endpoints are usually unauthenticated, fast and free of side effects.

---

### Q4. What status code should `POST /transactions` return on success, and why not 200?

**Model answer:**
**201 Created.** 200 OK means generic success. 201 says specifically that a new resource was created. The response usually includes the created resource (with its server-generated `id`) and optionally a `Location` header pointing to it, e.g. `/transactions/42`.

**Why it matters:** status codes are part of the API contract. Clients, SDK generators, API gateways, caches and monitoring all interpret them without parsing the body. Precise codes make an API predictable and self-documenting.

**Related codes to know:**

- `204 No Content`: successful DELETE with no body.
- `400 Bad Request`: malformed request.
- `422 Unprocessable Entity`: valid JSON that fails validation. FastAPI returns this by default.
- `401 Unauthorized`: not authenticated.
- `403 Forbidden`: authenticated but not allowed.
- `404 Not Found`: resource doesn't exist.
- `409 Conflict`: e.g. a duplicate.
- `500 Internal Server Error`: a server bug.

---

## Phase 1: Transactions API

### Q5. Why should money be stored as `Decimal` and not `float`?

**Model answer:**
Floats store numbers in base 2, and values like 0.1 have no exact base-2 representation, so they're stored as an approximation: `0.1 + 0.2 == 0.30000000000000004`. For money this is unacceptable — errors compound over millions of rows, equality comparisons fail, and reconciliation reports don't balance to the cent.

`Decimal` stores digits in base 10 with an explicit precision, scale and rounding mode, so `Decimal("0.1") + Decimal("0.2")` is exactly `Decimal("0.3")`. The Postgres equivalent is `NUMERIC(12, 2)`, which is exact; `FLOAT`/`DOUBLE PRECISION` are not.

**Alternative:** store integer cents (`4550` = $45.50), as Stripe does — exact and fast, at the cost of dividing by 100 everywhere.
**Trade-off:** `Decimal` is slower than `float`; that matters for scientific computing, never for transaction records.

---

### Q6. What does Pydantic do, and what happens on invalid data?

**Model answer:**
Pydantic is a data validation and parsing library driven by type hints. You declare the data's shape once and it generates the validation code. FastAPI uses that single declaration for four jobs:

1. **Parse** — JSON into Python objects (`"2026-09-14"` → `date`, `"45.50"` → `Decimal`)
2. **Validate** — enforce constraints such as `gt=0`, `min_length=1`
3. **Document** — generate the JSON Schema behind `/docs`
4. **Serialize** — convert the returned object back to JSON

On invalid data, Pydantic raises `ValidationError`; FastAPI catches it and returns **422** with a list of errors, each giving the field (`loc`), the message (`msg`) and the failed rule (`type`).

**Key insight:** validation runs _before_ your handler, so your business logic can assume valid data. That's "parse, don't validate" — push checks to the edge, keep the core clean.

**Alternatives:** hand-written `if` checks, marshmallow (Flask-era), plain dataclasses (typed but unvalidated). Pydantic v2's core is Rust, so it's fast.

---

### Q7. Why separate `TransactionCreate` and `Transaction` models?

**Model answer:**
It isn't "one for writing, one for reading" — `Transaction` is the _response_ shape, and POST returns it too. The reasons are:

1. **Different fields:** the client can't supply `id`; the server generates it. Later `user_id` and `created_at` join that list.
2. **Security:** with one shared model a client could POST `{"id": 999, "user_id": 42}` and overwrite server-controlled fields — the **mass assignment** vulnerability. With `user_id` it becomes access to another user's data.
3. **Hiding data:** a `User` response must never include `password_hash`.
4. **Independent evolution:** you can add a computed response field without changing what clients must send.

Mature codebases use `XCreate`, `XUpdate` (optional fields, for PATCH), `XResponse`, plus a separate database model.

---

### Q8. Path parameter vs query parameter?

**Model answer:**
It has nothing to do with reading vs writing — creation data travels in the **request body**.

- **Path parameter:** part of the URL path; identifies _which specific resource_. Required and hierarchical.
  `GET /transactions/42`, `GET /users/7/transactions`
- **Query parameter:** after `?` as key=value pairs; _filters, sorts or paginates_. Optional, order-independent.
  `GET /transactions?category=Groceries&limit=20&sort=date`

**Rule of thumb:** path = which resource; query = how to filter/sort/paginate the collection.

In FastAPI the split is automatic: an argument named in the route's `{braces}` is a path parameter; any other scalar argument is a query parameter.

**Practical consequence:** query strings appear in server logs and browser history — never put secrets or tokens in them.

---

### Q9. Why does in-memory data disappear on restart?

**Model answer:**
The `transactions` dict lives in the process's RAM. When the process exits, the OS reclaims that memory.

Two deeper problems interviewers look for:

- **It doesn't scale:** production runs several worker processes, each with its own dict. A POST handled by worker 1 is invisible to a GET served by worker 2.
- **No durability, concurrency control or query capability:** no transactions or rollback, no protection against concurrent mutation, no way to ask "sum by category for August".

**The principle:** keep application servers **stateless** and put state in a shared datastore. That's what allows horizontal scaling behind a load balancer.

---

### Bonus (from debugging): why did a typo return 500 instead of 404?

**Model answer:**
`transactions.het(...)` raised an `AttributeError` at runtime, and an unhandled exception becomes **500**. A 500 means _the server crashed_; a 404 is a deliberate decision. Python is dynamically typed, so a bad attribute name in a rarely executed branch only surfaces when that line runs — which is the argument for automated tests and a static type checker such as mypy.

### Bonus: why is `Decimal` serialized as a JSON string?

**Model answer:**
JSON has one number type and nearly every parser reads it as float64. Sending `45.50` as a bare number would let a JavaScript client's `JSON.parse` reintroduce the very rounding error `Decimal` avoids, and would drop the trailing zero (`45.5`). Pydantic v2 therefore serializes `Decimal` as a string, preserving both exactness and scale. The cost is that frontend code must handle a string; Stripe's integer-cents approach avoids the question entirely.
