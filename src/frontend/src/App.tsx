import AllConfigs from "./components/play_around";
import { handleSubmit } from "./components/submitData";

function App() {
  return (
    <div>
      <h1 style={{ textAlign: "center" }}>Microgrid Configuration</h1>
      <AllConfigs onSubmit={handleSubmit}/>
    </div>
  );
}

export default App;