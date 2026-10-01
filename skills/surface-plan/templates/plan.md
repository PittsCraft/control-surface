# Plan: <feature>

Revision <N>. Execution instructions for the agents, slice by slice. Written in the language `exploration.md` names in its repository rules: translate the headings, keep the markers as they are. Sources: `specs.md`, `exploration.md`, `interview.md`. Each section says what the feature needs and no more: one line when that is all there is. The plan stays alive: an executor that deviates amends it in the commit of its code.

## 1. Goal and scope

What the feature does, and what it explicitly does not. The acceptance criteria, copied from the specs and the interview, numbered.

## 2. Architecture decisions

Each decision with the options considered and why the others were set aside. The existing decisions of the repository that apply. The new ones that deserve a record of their own, in the repository's form.

## 3. Slices

Each slice ships and verifies alone, in order. Each is preceded by its marker, alone on its line and starting at the first column: the state script reads the list of slices from the markers, in any language. A slice number is never reused: a new slice takes a number above every number the plan has used. A marker quoted in prose is indented or kept inline.

<!-- slice:1 -->
### Slice 1: <title>

- Goal: what the slice delivers.
- Files: what it touches.
- Precedent: what it copies, or "none".
- Gates: the checks it runs, in the foreground.
- Done when: what proves it.
- Depends on: earlier slices, or nothing.

## 4. Tests

Per slice: unit tests; a property test for every invariant the specs state, with the tool the repository already uses; integration tests where a boundary is crossed; contract tests when a generated artifact changes; interface tests when the interface changes.

## 5. Definition of Done

The gates of section 7, green locally in the order CI runs them; regenerated artifacts committed with the change that forces them; the repository's conventions for branches, commits and pull requests; what is specific to this feature.

## 6. Risks and assumptions

What could sink the plan and how it is checked early. Every assumption taken instead of a question, with the reason it did not need the developer.

## 7. Gates

The commands that check the whole project, which the state script runs after the slices and at every fix, in order, stopping at the first that fails. Where they were found. One command per line in the block below, which starts at the first column and keeps its `gates` tag in any language. The block is empty when the project has none, and a sentence says so.

```gates
<command>
```
