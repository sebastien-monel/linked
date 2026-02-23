Notification.requestPermission().then((status) => {
  //if (status === "denied") {
  //}
  
  //if (status === "default") {
    //Notification.requestPermission(location.reload(true))
  //} 
  
  if (status === "granted") {
    const interval = setInterval(() => {
      const notifications_json = import( "/notifications.json", { with: { type: "json" } } );
      const notifications_tab = [] ;
      
      console.log(typeof notifications_json); 
      notifications_json.forEach((item, index) => {
          notifications_tab.push( new Notification("Brouillon :", {
            body: notifications_json[index]['body'], 
            tag : notifications_json[index]['tag']} 
          ))
      })
      
    }, 1000)
  }
})
