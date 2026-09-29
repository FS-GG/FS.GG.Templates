const app = document.querySelector("#app");

if (!(app instanceof HTMLElement)) {
  throw new Error("The application root is missing.");
}

const heading = document.createElement("h1");
heading.textContent = "Hello, world!";
app.append(heading);
