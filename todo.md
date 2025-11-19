let's add the voice, we have the endpoint in the index.html in /templates.

what we will need to start the voice server is :
- start Content\xVAsynth\resources\app\server.py
then inside teh server we will have /loadModel 
where we will need to laod the model located at Content\xVAsynth\resources\app\models\fallout4
look at Content\xVAsynth\resources\app\models\fallout4\f4_robot_assaultron.json it have inside the model info (modeltype etc...)

then when we need to synthetize a voice, we use /synthesizeSimple in serevr.py.

look at how the fucntion work to udnerstand how it will work, and make it compeltely functionnal

create a "voicemanager" python fiel on root,to handle all the voice action (starting server, loading model, synthetize the voice and playing the output.wav when ready etc...) the wav output shoudl be saved in /audio_output and played when the voice is ready.

here what xVAsynth said : "The tool is mainly built to be used via the accompanying UI. However, it can indeed also run headless (I know of people using it on a web hosted server), it's just that I haven't really designed it for that. You can start the server.exe (or if you want to manage your own dependencies, python server.py), and then you can call localhost requests from a separate script, to simulate the actions of the front-end UI. Have a look through the server.py and javascript files to see exactly what is needed for each call, but it's mostly just one localhost http call for loading a model, and then another call for each inference"
we will sue it headless (so directly using server.py)

but look at how server.py work first.










by doing this cd "Content/xVAsynth/resources/app" && ./cpython_cpu/server.exe
we start the server

by doing this curl -X POST "http://localhost:8008/loadModel" -H "Content-Type: application/json" -d "{\"modelType\": \"xVAPitch\", \"model\": \"models/fallout4/f4_robot_assaultron\", \"pluginsContext\": \"{}\", \"base_lang\": \"en\"}" 

we manage to laod the correct voice model!

by doing that curl -X POST "http://localhost:8008/synthesizeSimple" -H "Content-Type: application/json" -d @synthesis_request.json
we manage to generate the voice file !


now, we just need to implement all that in voicemanager.py
basically just start the server, make the POST query to laod the model, and then do the POST request with the same data as in the synthesis_request.json but with "sequence" with as the text in the prompt