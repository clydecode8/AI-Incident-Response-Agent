from pathlib import Path

JAVA_SRC_DIR = Path("incident-demo/src/main/java")

def search_codebase(query: str, max_results: int = 5) -> str:
    keywords = [
        word.lower()
        for word in query.replace(".", " ").replace(":", " ").split()
        if len(word) >= 4
    ]

    results = []

    for file in JAVA_SRC_DIR.rglob("*.java"):
        lines = file.read_text(encoding="utf-8", errors="ignore").splitlines()

        for i, line in enumerate(lines, start=1):
            text = line.lower()

            if any(k in text for k in keywords):
                start = max(1, i - 3)
                end = min(len(lines), i + 3)

                snippet = "\n".join(
                    f"{n}: {lines[n-1]}"
                    for n in range(start, end + 1)
                )

                results.append(f"\nFile: {file}\n{snippet}")

                if len(results) >= max_results:
                    return "\n".join(results)

    return "No matching Java code found."