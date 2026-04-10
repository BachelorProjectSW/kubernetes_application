// things to handle:
//send data til backend  ( tjek om den gør dette )
// lav resten af experiemtn tingende 
// tjekke at configurationer er det samme for det sammen experiement id (gør i backend)
// refactor = del det op i flere filer. 
// lav endpoint i backend. hvor navn er save-config 
import { useState } from 'react';
import Ids from './experimentID';
import Start from './startTime';

function allConfigs(handleSubmit) {
    const [inputs, setInputs] = useState({});

    const handleChange = (e) => {
        const { name, value } = e.target;

        setInputs(values => ({ ...values, [name]: value }));
    };

    return (
        <form onSubmit={(e) => handleSubmit(e, inputs)}>
            <div style={{ marginBottom: "20px" }}>
                <Ids
                    inputs={inputs}
                    setInputs={setInputs}
                    handleChange={handleChange}
                />
            </div>
            <br/>

            <label> Name:
                <input
                    type="text"
                    name="name"
                    value={inputs.name || ""}
                    onChange={handleChange}
                />
            </label>
            <br/>
            <div>
                <Start
                    inputs={inputs}
                    handleChange={handleChange}
                />
            </div>

            <br />

            <button type="submit"> Save configurations</button>
        </form>
    );

}
export default allConfigs;