---
name: commit
description: Write the commit message for work just finished. Use at the end of any prompt that changed a file, before handing the message to the developer.
---

# Writing a commit message

The order to do it in. The `report` skill carries the report this message
goes at the end of.

## 1. Read what changed

```bash
git diff --stat
git diff | grep "^[-+]def \|^[-+].*CREATE TABLE \|^[-+]@router\."
```

The second command lists the symbols that moved. Those are the bullets.

## 2. Check any claim before making it

`git show HEAD:<file>` settles what was already there.

## 3. Write it in the shape

It makes past work findable from `git log`.

Subject line: `<area>: <what changed>`, imperative, under 72 characters. Then a
blank line, a paragraph, a bulleted list, and the trailers.

The paragraph carries the symptom and the decision.

The bullets name every table, column, function, route, index, and value the
commit adds or removes — one line each, unwrapped, the identifier backticked.
A consequence somewhere the diff does not touch gets a bullet of its own.

Name every removal. `bin/check-commit <message-file>` reads the diff and
reports the ones a message leaves out.

Check a claim before making it. `git show HEAD:<file>` settles whether a
column was added or was already there.

```
scheduler: fold business_users into employees

An employee resolved as a customer: whoami read business_users, which only
operators had, so the employee branch had never been reachable. A one-person
business needed a row in each table for one person.

- Drop `business_users`, `BusinessUserRow`, and the `superadmin` role value it carried
- `employees` gains `role` (operator | employee); `user_id` was already there
- Remove `insert_business_user`, `get_business_user`, `get_business_user_for`
- Add `insert_employee_member`, `get_employee_for_business`
- Add `is_working_for_business(business_id, user_id)` — the question every business-scoped route asks
- `is_operator_of` takes the business first
- `link_employee_to_user` refuses an account that already works somewhere
- Add `uq_employees_user_id`: one business per account
- `sign_up` writes the owner's employee record, so the owner appears in the Employees list — where a solo business ticks `includeInSchedule`

App: io.bithead.scheduler
Feature: employees
Feature: roles
Decision: an operator holds the operator role on an employees row
Decision: role is stored lower case, the ACL label being a separate string
Rule: scope before identity, so is_operator_of takes the business first
```

```
scheduler: fold business_users into employees

An employee resolved as a customer: whoami read business_users, which only
operators had, so the employee branch had never been reachable. A one-person
business needed a row in each table for one person.

- Drop `business_users`, `BusinessUserRow`, and the `superadmin` role value it carried
- `employees` gains `role` (operator | employee); `user_id` was already there
- Remove `insert_business_user`, `get_business_user`, `get_business_user_for`
- Add `insert_employee_member`, `get_employee_for_business`
- Add `is_working_for_business(business_id, user_id)` — the question every business-scoped route asks
- `is_operator_of` takes the business first
- `link_employee_to_user` refuses an account that already works somewhere
- Add `uq_employees_user_id`: one business per account
- `sign_up` writes the owner's employee record, so the owner appears in the Employees list — where a solo business ticks `includeInSchedule`

App: io.bithead.scheduler
Feature: employees
Feature: roles
Decision: an operator holds the operator role on an employees row
Decision: role is stored lower case, the ACL label being a separate string
Rule: scope before identity, so is_operator_of takes the business first
```

**Trailers.** `Key: value`, one per line, at the end. Repeat a key freely —
that is what makes them queryable. These four are the set:

| Key | What goes in it |
|---|---|
| `App` | Bundle id, when the work belongs to one app |
| `Feature` | The thing a person would search for later. One per line |
| `Decision` | A choice made that could reasonably have gone the other way |
| `Rule` | A rule written into `docs/prompt/` by this change |

Omit a key with nothing to say. Stretch for `Decision` and `Rule` — they answer
"why is it like this" long after the diff stops being readable.

Counts belong in the report above. A trailer carries what a future `git log`
would search for.

**Before handing the message over**, run it:

```bash
bin/check-commit <message-file>            # against the working tree
bin/check-commit --cached <message-file>   # against what is staged
```

**What it buys:**

```bash
git log --grep="Feature: customers"        # every time we touched customers
git log --grep="^Decision:"                # every decision, ever
git log --grep="App: io.bithead.scheduler" # everything in one app
```

## 4. Run the check

```bash
bin/check-commit <message-file>
```

It reports removals the message left out.

## 5. Hand it over

The developer commits. Give them the message in a fenced block.

## When a correction comes back

Rewrite the message. Adding to it turns the message into a changelog and
buries the paragraph that mattered.
