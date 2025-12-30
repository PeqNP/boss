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

TBD: Define all patterns that may not be standard in the provided guidelines, but the project is using. Some of the project may not be using the correct standard for function comments.

When creating new `UIController`s (Javascript and HTML) please use the standard as set forth by BOSS. Refer to controllers in `/public/boss/app/io.bithead.boss/controller` for examples.
