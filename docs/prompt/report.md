# Reporting Work

Work gets a report. Any prompt that changed something ends this way, whatever
layer it touched — Python, JavaScript, Swift, a document, a tool.

## The sections, in this order

Paths and behaviour first — that is what was asked for. What was learned comes
after. What the developer has to decide comes last, where they will still be
reading.

### What was tested

One bullet per path, each reading *situation → outcome*. Happy paths and
exception paths in the same list, grouped by feature, and name the exception:

```
**Sending a verification code to get back into a booking**
- Customer gave a phone number → code sent by SMS
- Customer gave neither a phone nor an email → `NoContactChannel`, nothing sent
- Job code matches no appointment → `JobNotFound`, nothing sent
```

Where the work has no tests — a UI change, a document, a tool — this becomes
**What changed**, one bullet per thing, each written as behaviour:

```
- The Manage menu opens Setup Assistant last, after a separator
- A list box sized `auto` sits inside its window; `100%` overflows the border
```

### Tests

The total, and that they pass. State that each rule was broken deliberately and
a test caught it, with the mutation count.

Everything passes before moving on.

### What I found along the way

Mistakes made, surprises, anything left without a consumer. A wrong assertion,
a check that turned out to run on nothing, a counter nothing reads yet, a bug
found in passing.

Fill this by rereading the work.

### What I need from you

For a decision that is genuinely the developer's. Five short parts, in this
order, and the last two matter most:

- *The context.* Where the decision bites, in plain language.
- *What the source says.* Quote the plan's Open Decision, or the rule, verbatim
  — they wrote it, and the wording is the question.
- *Why it is a tradeoff.* Each option with its real consequence. Say which
  consequences are mild — that is usually what decides it.
- *What is actually needed.* The question on its own, in a sentence.
- *What changes when they answer.* Which file, and what stands either way.

Recommend an option.

### Commit message

Last, in a fenced block, ready to paste.

## The commit message

It makes past work findable from `git log`.

Subject line: `<area>: <what changed>`, imperative, under 72 characters. Then a
blank line, a paragraph, a bulleted list, and the trailers.

The paragraph carries the symptom and the decision.

The bullets name every table, column, function, route, index, and value the
commit adds or removes — one line each, the identifier backticked. A
consequence somewhere the diff does not touch gets a bullet of its own.

Name every removal. `bin/check-commit <message-file>` reads the diff and
reports the ones a message leaves out.

Check a claim before making it. `git show HEAD:<file>` settles whether a
column was added or was already there.

```
scheduler: fold business_users into employees

An employee resolved as a customer: whoami read business_users, which only
operators had, so the employee branch had never been reachable. A one-person
business needed a row in each table for one person.

- Drop `business_users` and the `superadmin` role value it carried, with
  `BusinessUserRow`
- `employees` gains `role` (operator | employee); `user_id` was already there
- Remove `insert_business_user`, `get_business_user`, `get_business_user_for`
- Add `insert_employee_member`, `get_employee_for_business`
- Add `is_working_for_business(business_id, user_id)` — the question every
  business-scoped route asks
- `is_operator_of` takes the business first
- `link_employee_to_user` refuses an account that already works somewhere
- Add `uq_employees_user_id`: one business per account
- `sign_up` writes the owner's employee record, so the owner now appears in
  the Employees list — where a solo business ticks `includeInSchedule`

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

The developer commits. Write the message and hand it over.

## Notes

Report what happened. Failing tests come with their output. Work left aside is
named, with the reason.
