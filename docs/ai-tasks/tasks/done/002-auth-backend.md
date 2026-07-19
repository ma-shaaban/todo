# 002 — Auth backend (email + password, cookie sessions)

Signup/login/logout/me with argon2id hashing, server-side 30-day rolling sessions,
login rate limiting, Origin-check CSRF guard. `users.provider` reserves the Google
OAuth slot (owner will add credentials later; see task 008's setup doc).

- **Status:** DONE (PR #7, merged as `a39f095`; staging verified — `/api/auth/me`
  401, real signup 201).
- Adversarial review confirmed + fixed 6 majors: login timing oracle (dummy-hash
  equalization), leftmost-XFF rate-limit bypass (rightmost entry + per-email
  backstop), commit-after-response phantom successes (function-scoped dependency),
  rolling expiry never re-issuing the cookie, unescaped DB password in URL
  (URL.create), permanent auth outage when startup migrations fail (background
  retry loop in entrypoint + JSON 503 handlers).
- 27 tests cover the flows and each fixed finding.
