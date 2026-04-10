import { useState } from "react";
import earlierExpIds from './staticData';

function Ids({ inputs, setInputs, handleChange }) {

    const [isExisting, setIsExisting] = useState(false);
    const toggleMode = () => setIsExisting(!isExisting);

    const handleSelectHistory = (e) => {
        const selectedId = e.target.value;
        if (!selectedId) return;

        const historicalData = earlierExpIds.find(exp => exp.id == selectedId);

        if (historicalData) {
            setInputs(prev => ({
                ...prev,
                expID: historicalData.id,
                name: historicalData.name,
                startDate: historicalData.startDate,
                duration: historicalData.duration
            }));
        }
    };


    return (
        <>
            < label > ExpId:</label >
            <button type="button"
                onClick={toggleMode}
                style={{ marginLeft: "10px", fontSize: "0.8em" }}
            >
                {isExisting ? "Switch to New ID" : "Select Existing ID"}
            </button>

            <br />

            {
                isExisting ? (
                    <select name="expID" onChange={handleSelectHistory}>
                        <option value="">-- Select an ID --</option>
                        {earlierExpIds.map(exp => (
                            <option key={exp.id} value={exp.id}>{exp.id}</option>
                        ))}
                    </select>
                ) : (
                    <input
                        type="text"
                        name="expID"
                        value={inputs.expID || ""}
                        onChange={handleChange}
                    />
                )
            }
        </>
    );

}

export default Ids;
