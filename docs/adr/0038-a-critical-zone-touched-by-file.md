# 0038. A critical zone is touched by file

Status: accepted
Date: 2026-10-08

## Context

The developer reads the code of the critical zones the host declares, from the list of files the reviewer leaves at conformity, and the blueprint tells them at approval which zones the plan touches. The two were read differently: the extractor and the cross-check read a zone as what it protects, the reviewer as the files that hold its code.

In 10 of the 27 runs of the evaluations that reached conformity, the page the developer approved said that the plan touches no critical zone, and the hand back at conformity sent them to read a file of one (#107). A developer who trusts the page takes that list for a mistake.

Two other ways were open. The reviewer could list a file only when the lines the branch changed belong to the zone: the list is shorter and agrees with the page, and a reviewer that misjudges hides code the developer was to read, which the script cannot check. Or both readings could stay, with the hand back saying why: the page approved would still have said none.

## Decision

A zone is touched as soon as the plan changes a file that holds its code, and the blueprint says how far the change goes: into what the zone protects, or only into something else the file holds.

The extractor, the cross-check and the reviewer hold one definition of such a file, in the same words. It is a file the host places in the zone, by its name, its folder or a pattern, or one whose code defines or computes what the zone protects. Among the files the host does not place, one that only uses that code, tests it or describes it does not hold it.

A zone the page says is not touched is held as the contract: a branch or an amendment that changes a file of it is a break, and the developer decides.

## Consequences

The page says "touched" for a change that leaves the rule of a zone alone, and says so. A fix or an amendment that reaches a zone the page said was not touched stops the loop on a plan change proposal, where the file was listed without a word.

The definition is narrow on purpose. A wider wording announced a zone for a file that prints a fine and for a test file, and listed a README that states the fields of a format: the developer was sent to read as critical code what holds none.

The three prompts carry the definition word for word, so a change to one is a change to all three, and the evaluations measure both ends: every file listed was announced, and every file announced is listed.
