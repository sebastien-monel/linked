Notification.requestPermission().then((status) => {
  //if (status === "denied") {
  //}
  
  //if (status === "default") {
    //Notification.requestPermission(location.reload(true))
  //} 
  
  if (status === "granted") {
    const interval = setInterval(() => {
      const data = await import( "/notifications.json", { with: { type: "json" } } );
      const notification = new Notification("Brouillon :", {body: "Hi there !!!", tag : "1"} );
    }, 1000)
  }
})
