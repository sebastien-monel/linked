Notification.requestPermission().then((status) => {
  //if (status === "denied") {
  //}
  
  //if (status === "default") {
    //Notification.requestPermission(location.reload(true))
  //} 
  
  if (status === "granted") {
    const interval = setInterval(() => {
      const response = fetch("/notifications.json");
      
      if (!response.ok) {
        throw new Error(`Response status: ${response.status}`);
      }

      const result = response.json();
      
      console.log(typeof result); 
      console.log(result); 
      
      const notifications_json = import( "/notifications.json", { with: { type: "json" } } );
      const notifications_tab = [] ;
      
      console.log(typeof notifications_json); 
      console.log(notifications_json); 

      //notifications_json.forEach((item, index) => {
      for (const notification of notifications_json) {
          notifications_tab.push( new Notification("Brouillon :", {
            body: notification['body'], 
            tag : notification['tag']} 
          ))
      }
    }, 1000)
  }
})
