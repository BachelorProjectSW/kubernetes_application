function Question({inputs, handleChange}){

    return(
         <div style={{ border: "1px solid #ccc", padding: "10px", marginTop: "10px" }}>
            <p> Question for LLM</p>

            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <label> question</label>
                    <input 
                        type="text"
                        name="question"
                        value={inputs.question}
                        onChange={handleChange} />
                
            </div>
             <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <label>max output tokens</label>
                    <input
                        type="number"
                        name="max_output_tokens"
                        value={inputs.max_output_tokens} 
                        onChange={handleChange}/>
             </div>
        </div>
    );
}


export default Question; 