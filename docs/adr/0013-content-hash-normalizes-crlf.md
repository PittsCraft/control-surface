# 0013. Content hash: SHA-256 with CRLF read as LF

Status: accepted
Date: 2026-09-29

## Context

Approval designates a content by its hash, and the guards compare the hash of `overview.md` recorded at approval with the current one. A rebase, a squash or a checkout on Windows with `core.autocrlf` changes line endings without changing the text. A hash of the raw bytes would then read as an amendment of a frozen overview and block the plan.

## Decision

The hash of a file is `sha256:` followed by the 64 lower case hexadecimal digits of the SHA-256 of its bytes, after every `\r\n` has been replaced by `\n` (`plan_folder.content_hash`). A lone `\r` is left alone: it is content, not an ending of any platform the chain targets. The digest is computed on bytes, so the encoding of a file is never guessed.

## Consequences

The same text with LF, CRLF or mixed endings has one hash, which a property test checks. A change that only converts endings never blocks a plan, and a change of any other byte always does. The one blind spot is a file whose meaning depends on the difference between `\r\n` and `\n`, which the Markdown files of a plan do not.
