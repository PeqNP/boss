# Coding Style

## Python Style Guide

For Python, use [PEP 8](https://peps.python.org/pep-0008/). Python is used only for private web services.

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
