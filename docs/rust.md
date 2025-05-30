# Rust

Create a new project

```
cargo new <project_name>
```

Build a project

```
cd <project_name>
cargo build
```

Run a project

```
./target/debug/<project_name>
# OR
cargo run
```

Check if project will compile

```
cargo check
```

Functions

```
// Borrows `s` for reading
fn first_word(s: &str) -> &str {
    // ...
}

let s = "Hello, world";
// `y` contains immutable reference to a value within `s`
let y = first_word(&s);
```

Debugging output

```
let s = "Hello, world";
println!(s);
dbg!(&s); // Prints line number
```

Structures

```
struct Rectangle {
    width: u32,
    height: u32,
}

impl Rectangle {
    fn area(&self) -> u32 {
        self.width * self.height
    }
}
```

Enums

```
enum IpAddr {
    v4(u8, u8, u8, u8),
    v6(String),
}

impl IpAddr {
    fn route(&self) {
        // ...
    }
}

let home = IpAddr::v4(127, 0, 0, 1);
let loopback = IpAddr:v6(String::from("::1"));

fn route(ip_addr: &IpAddr) { }

route(home);
route(loopback);

home.route();
```

Optional types

```
let num = Some(5);
let cha = Some('e');

// Can't infer if default value is None. Therefore, type is provided.
let absent: Option<i32> = None;

// When wanting to access value within Option
// This works with `num` and `absent`
fn plus_one(x: Option<i32>) -> Option<i32> {
    match x {
        None => None,
        Some(i) => Some(i + 1),
    }
}

```

Matching enums

```
enum Coin {
    Penny,
    Nickel,
    Dime,
    Quarter,
}

// Succinct
fn value_in_cents(coin: Coin) -> u8 {
    match coin {
        Coin::Penny => 1,
        Coin::Nickel => 5,
        Coin::Dime => 10,
        Coin::Quarter => 25,
    }
}

// Expressive (more than one lines for case)
fn value_in_cents(coin: Coin) -> u8 {
    match coin {
        Coin::Penny => {
            println!("Lucky penny!");
            1
        }
        Coin::Nickel => 5,
        Coin::Dime => 10,
        Coin::Quarter => 25,
    }
}
```

Matching enums with associated values

```
#[derive(Debug)] // so we can inspect the state in a minute
enum UsState {
    Alabama,
    Alaska,
    // --snip--
}

enum Coin {
    Penny,
    Nickel,
    Dime,
    Quarter(UsState),
}

fn value_in_cents(coin: Coin) -> u8 {
    match coin {
        Coin::Penny => 1,
        Coin::Nickel => 5,
        Coin::Dime => 10,
        Coin::Quarter(state) => {
            println!("State quarter from {state:?}!");
            25
        }
    }
}
```

Matching catch-all patterns

```
let dice_roll = 9;
match dice_roll {
    3 => add_fancy_hat(),
    7 => remove_fancy_hat(),
    // other must be last arm. Otherwise, it would terminate prematurely.
    other => move_player(other),
}

fn add_fancy_hat() {}
fn remove_fancy_hat() {}
fn move_player(num_spaces: u8) {}
fn reroll() {}

// This is the same thing. Notice the underscore
match dice_roll {
    3 => add_fancy_hat(),
    7 => remove_fancy_hat(),
    _ => reroll(),
}

// This will do nothing if match isn't made
match dice_roll {
    3 => add_fancy_hat(),
    7 => remove_fancy_hat(),
    _ => (),
}
```

if let Option matching

```
let config_max = Some(3u8);
if let Some(max) = config_max {
    println!("The maximum is configured to be {max}");
}

// Using UsState from previous example, this shows how we can more succinctly
// extract a value from Option.
impl UsState {
    fn existed_in(&self, year: u16) -> bool {
        match self {
            UsState::Alabama => year >= 1819,
            UsState::Alaska => year >= 1959,
            // -- snip --
        }
    }
}

fn describe_state_quarter(coin: Coin) -> Option<String> {
    let state = if let Coin::Quarter(state) = coin {
        state
    } else {
        return None;
    };

    if state.existed_in(1900) {
        Some(format!("{state:?} is pretty old, for America!"))
    } else {
        Some(format!("{state:?} is relatively new."))
    }
}

// OR a more succinct version. (Similar to a guard let)

fn describe_state_quarter(coin: Coin) -> Option<String> {
    let Coin::Quarter(state) = coin else {
        return None;
    };

    if state.existed_in(1900) {
        Some(format!("{state:?} is pretty old, for America!"))
    } else {
        Some(format!("{state:?} is relatively new."))
    }
}
```

Usin
