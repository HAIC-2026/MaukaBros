# District Insight: security and privacy

## In short

**No personal data.** District Insight only holds published statistics about whole districts,
counties and the state, plus program rules quoted from official documents. There are no
accounts, logins or cookies.

**What goes to Anthropic.** When someone asks the research assistant a question, the server
sends Claude (Anthropic's API):

- the question
- the district selected on the page
- up to the last 12 messages of the conversation
- the public figures the assistant looks up

Nothing else leaves the server. The assistant panel and every page footer say this, and ask
people not to include personal details. The footer also notes that loading the map and fonts
shares a visitor's IP address with Esri and jsDelivr, as loading any file from them does.

**What is kept.** The site doesn't save questions or answers. The conversation lives only in the
open page and is gone on reload. A question opened in a report travels through the browser's own
storage, never the link, and is deleted once shown. The database is opened read-only. The
Anthropic key stays on the server, in `.env`, which has never been committed to git.

**What protects the AI budget**

- per-visitor, hourly and daily limits on questions (IPv6 visitors counted per /64 network)
- a daily and a per-question spending cap in dollars, estimated from each response's token counts
- size limits on every request, applied while the request is read

**What protects the answers**

- Signed answers: a browser can't invent earlier assistant replies to steer the model.
- Read-only tools: the assistant can't change any data.
- Number check: every number in an answer is compared with the data the assistant looked up, and
  any that don't match are shown under the answer as "not found in the data".

**What protects the figures and the page**

- Source files are checksummed, and the build refuses a file that has changed.
- 51 validation checks, including an exact match with DBEDT's published district profiles, must
  pass before a new database is used.
- Every figure is put on the page as text, never as HTML.
- A Content Security Policy allows scripts only from this site and Esri's map library, and blocks
  framing by other sites.

## Assistant limits

Set in `.env` (see `.env.example`). The defaults are below.

| Limit                                       | Default            | Setting                            |
| ------------------------------------------- | ------------------ | ---------------------------------- |
| Questions per visitor per minute / per hour | 10 / 60            | `CHAT_PER_MINUTE`, `CHAT_PER_HOUR` |
| Answers being worked on at once             | 4                  | `CHAT_MAX_CONCURRENT`              |
| Questions per day, all visitors             | 500                | `CHAT_DAILY_LIMIT`                 |
| AI spending per day, all visitors           | $5.00              | `CHAT_DAILY_USD`                   |
| AI spending for one question                | $0.50              | `CHAT_QUESTION_USD`                |
| Question length                             | 1,000 characters   | fixed                              |
| Conversation sent back                      | 12 messages, 64 KB | fixed                              |

Spending is estimated from Claude Opus 5.5 list prices (`CHAT_PRICE_*`); update them if the model
or prices change. Limits are kept in memory and reset when the server restarts. A forwarded-address
header is trusted only when `TRUST_PROXY=1`, so it can't be used to dodge the limits.

## Where to find each control

| Control                                 | Code                                                                     |
| --------------------------------------- | ------------------------------------------------------------------------ |
| Read-only database                      | `query()` in `api/main.py`                                               |
| Message roles, counts and lengths       | `ChatRequest` and `chat()` in `api/main.py`                              |
| Request body cap (incl. chunked)        | `ChatBodyLimit` in `api/security.py`                                     |
| Question and visitor limits             | `ChatLimiter`, `visitor_id` in `api/security.py`                         |
| Spending caps                           | `SpendBudget` in `api/security.py`, checked in `answer()` in `api/agent.py` |
| Signing and checking answers            | `sign_answer` / `verify_answer` in `api/security.py`                     |
| Number check                            | `api/answer_check.py`, shown by `web/js/map-page.js`                     |
| Security headers                        | `SecurityHeaders` in `api/security.py`                                   |
| Generic error messages                  | `chat()` and `query()` in `api/main.py` (details go to the server log)   |
| Text-only rendering                     | `web/js/markdown.js`, `el()` in `web/js/render.js`                       |
| Question hand-off to reports            | `reportUrl` / `takeQuestion` in `web/js/render.js`                       |
| Pinned dependencies                     | `requirements.txt`                                                       |
| Source file checksums                   | `pipeline/raw/manifest.yaml`, checked in `pipeline/context.py`           |

Test the controls offline, with no paid AI calls (35 checks):

```
python validation/test_security.py
```

## Before going live

- Serve over HTTPS behind a reverse proxy, without `--reload`; set `TRUST_PROXY=1` there.
  The site adds `Strict-Transport-Security` automatically once requests arrive over HTTPS.
- Keep `ANTHROPIC_API_KEY` in the host's secret store and set a monthly spending limit in the
  Anthropic console as a second cap.
- Set `API_DOCS=0` to turn off the interactive API docs.
- Restrict the Esri API key to the site's domain once it's issued.
