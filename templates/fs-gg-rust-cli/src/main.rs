#![forbid(unsafe_code)]
fn polyglot_greet(name: &str) -> String {
    format!("hello {name}")
}
fn main() {
    let mut args = std::env::args().skip(1);
    let command = args.next().unwrap_or_else(|| "hello".into());
    if command != "hello" {
        eprintln!("requested failure");
        std::process::exit(2);
    }
    println!("{}", polyglot_greet(&args.next().unwrap_or_else(|| "world".into())));
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn literal_domain() {
        assert_eq!(polyglot_greet("$(literal);& with spaces"), "hello $(literal);& with spaces");
    }
}
