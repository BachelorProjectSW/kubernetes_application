// things to handle:
//send data til backend  ( tjek om den gør dette )
// et problem der sker er at tidligere experimenters data godt kan overgå det der allerede eksister. 
// lav resten af experiemtn tingende 
// tjekke at configurationer er det samme for det sammen experiement id (gør i backend)
// refactor = del det op i flere filer. 
// lav endpoint i backend. hvor navn er save-config 
//
import { useState } from 'react';
import Ids from './experimentID';
import Start from './startTime';
import Weights from './weights';
import Power_schedular from './power_schedular';
import Workload from './workloadbalance';
import ClusterMangening from './cluster';
import GlobalScheduler from './global_schedular';
import StratoConfigs from './strato_config';

function allConfigs({ onSubmit }) {
    const [inputs, setInputs] = useState({});

    const handleChange = (e) => {
        const { name, value } = e.target;

        setInputs(values => ({ ...values, [name]: value }));
    };

    return (
        <form onSubmit={(e) => onSubmit(e, inputs)}>
            <div style={{ marginBottom: "20px" }}>
                <Ids
                    inputs={inputs}
                    setInputs={setInputs}
                    handleChange={handleChange}
                />
            </div>
            <br />

            <label> Name:
                <input
                    type="text"
                    name="name"
                    value={inputs.name || ""}
                    onChange={handleChange}
                />
            </label>
            <br />
            <div>
                <Start
                    inputs={inputs}
                    handleChange={handleChange}
                />
            </div>

            <br />

            <div>
                <Weights
                    inputs={inputs}
                    handleChange={handleChange}
                />
            </div>

            <div>
                <Power_schedular
                    inputs={inputs}
                    handleChange={handleChange}
                />
            </div>

            <br />

            <div>
                <label> max latency in ms:
                    <input
                        type="number"
                        name="max_latency"
                        value={inputs.max_latency || ""}
                        onChange={handleChange}
                    />
                </label>
            </div>

            <div>
                <Workload
                    inputs={inputs}
                    handleChange={handleChange}
                />
            </div>

            <div>
                <ClusterMangening
                    inputs={inputs}
                    setInputs={setInputs}
                    />
            </div>
            <div>
                <GlobalScheduler
                    inputs={inputs}
                    handleChange={handleChange}
                    />
            </div>
             <div>
                <StratoConfigs
                    inputs={inputs}
                    handleChange={handleChange}
                    />
            </div>

            <button type="submit"> Save configurations</button>
        </form>
    )
}
export default allConfigs;