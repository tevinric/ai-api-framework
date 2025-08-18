You are given my ai api code base. 

You need to assist me with the apis/speech_services in the following mannnger: 

Current implementation:

1. When a user submits a request to the stt speech services, an async job is created
2. The log gets addded the the user_usage table to log which user called the service
3. The backround job then processes the audio file for transcription
4. Because the log is happeninng at the start when the job is submitted, the length of the audio file in seconds is not being logged. This is a critical piece of information as it will be used for billing. 
5. Furthermore when the MS speech service completes it is not returning the duration of the processed audio file in seconds. The api response always shows 0 seconds in the value field. 


Your task: 
1. Ensure that the audio processing api function gets the audio seconds from the processed file and includes this in the api response.
2. If the MS api returns 0 seconds then use a native library for accurately determining the lenght of the audio file processed. 
3. The app is deployed to a linux system so ensure that whatever you choose to use is compatiable with linux and must be included in the dockerfile. Please also use something that can be run on a windows system (during development and testing)
4. you must also ensure that the log gets created ONLY after the audio file is processed so that it has the duration in seconds of the audio file. 
5. The log must accurately capture the lenght of the audio file. 


Please make the relevant changes to safely implemnt these fixes in my code base without impacting the rest of the apis
