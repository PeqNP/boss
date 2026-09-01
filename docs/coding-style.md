# Coding Style

## Python Style Guide

For Python, use [PEP 8](https://peps.python.org/pep-0008/), with one
departure. Python is used only for private web services.

### Wrapping a signature or a call

A signature or a call that does not fit within 80 columns breaks with the
parenthesis last, one argument to a line, and the closing parenthesis on a line
of its own:

```python
async def update_job(
    business_id: int,
    job_id: int,
    boss_user: User,
    request: Request,
    body: JobBody
):
```

PEP 8 also allows a hanging indent aligned to the opening parenthesis. We do
not, because it stops saying which argument belongs to which call as soon as
anything nests:

```python
        confirmationSentTo=ConfirmationSentTo(sms=sent.get("sms"),
                                              email=sent.get("email"))
                           if sent else None
```

The same call under this rule, where the nesting is the indentation:

```python
        confirmationSentTo=ConfirmationSentTo(
            sms=sent.get("sms"),
            email=sent.get("email")
        )
        if sent else None
```

A construct with one argument is left alone however long it is — wrapping a
single value buys nothing.

### Constants

A module's constants go under its imports, above every function and class. They are part of what the module is rather than part of how it works, and scattered through a file they are found by searching instead of by reading.

A constant is not read out of another module. `lib.OPERATOR` binds the caller to a name the module happens to hold; `lib.is_operator_role(role)` says what the caller wanted, and leaves the module free to answer it differently later.

`bin/check-format` reports both as warnings rather than errors: the tree predates the rule, and a constant sitting beside what it serves deserves a judgement of its own before it moves.

`bin/check-format` reports what breaks the wrapping rule, and `--fix` rewrites it. It
compares the parse tree before and after, so a rewrite that would change what
the code means is refused rather than saved.

## Swift Style Guide

Please use Google's [Swift Style Guide](https://google.github.io/swift/). Swift is used for the primary web server. The Python private web services may communicate directly with this service to validate and retrieve user credentials.

## Javascript Style Guide

Please use Google's [Javascript Style Guide](https://google.github.io/styleguide/jsguide.html). Javascript is used only for frontend development.

## Override Style Guide for Swift and Javascript

If statements shall break the `if`, `else`, and `else if` blocks on their own new line as follows:

```swift
if true {
    // Execute if statement is true
}
else {
    // Execute if statement is false
}
```

The same holds for Javascript, along with the rest of the project's Javascript
conventions — template literals over concatenation, emptiness checks, early
returns, and the component APIs — which live in
[`docs/prompt/shared.md` § Coding Rules and Conventions](prompt/shared.md#16-coding-rules-and-conventions).
