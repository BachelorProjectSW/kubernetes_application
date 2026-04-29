function Question({ inputs, handleChange }) {
    
    return (
        <>
            <p className="panel-title">
                <span className="panel-title-icon">🤖</span>
                LLM Query
            </p>

            <div style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap", alignItems: "flex-start" }}>
                <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem", flex: "1 1 300px" }}>
                    <span style={{ fontSize: "0.68rem", color: "var(--text-label)", letterSpacing: "0.04em" }}>
                        Prompt / Question
                    </span>
                    <input
                        type="text"
                        name="question"
                        value={inputs.question || ""}
                        onChange={handleChange}
                        placeholder="Enter the prompt sent to the LLM..."
                        style={{ width: "100%" }}
                    />
                </label>

                <label style={{ display: "flex", flexDirection: "column", gap: "0.35rem", flex: "0 0 160px" }}>
                    <span
                        data-tooltip="Maximum tokens the LLM may generate per response"
                        style={{ fontSize: "0.68rem", color: "var(--text-label)", letterSpacing: "0.04em" }}
                    >
                        Max Output Tokens
                    </span>
                    <input
                        type="number"
                        name="max_output_tokens"
                        value={inputs.max_output_tokens || ""}
                        onChange={handleChange}
                        placeholder="e.g. 512"
                        style={{ width: "100%" }}
                    />
                </label>
            </div>
        </>
    );
}

export default Question;
