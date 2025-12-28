import {forceSimulation, forceCollide, forceX} from "https://cdn.jsdelivr.net/npm/d3-force@3/+esm";

const params = new URLSearchParams(document.location.search);

let node_id;
if (params.has("node_id")) {
    node_id = params.get("node_id");
} else {
    node_id = "1";
}

let url = "".concat("/", node_id, "/data.json");

const data = await d3.json(url);
const nodes = data.nodes;
const links = data.links;
//  const types = Array.from(new Set(links.map(d => d.type)));
console.log(nodes);
console.log(links);

// Declare the chart dimensions and margins.
const width = document.body.offsetWidth; //640;
const height = document.documentElement.offsetWidth * 9 / 16; //400;
const marginTop = 20;
const marginRight = 20;
const marginBottom = 30;
const marginLeft = 40;

//prepare colors
const color_node = d3.scaleOrdinal(d3.schemeCategory10);
const color_link = d3.scaleOrdinal(d3.schemeCategory10);

//const nodes = [{}, {}];
const simulation = forceSimulation(nodes)
    .force("link", d3.forceLink(links).id(d => d.id))
    .force("x", forceX())
//    .force("y", forceY())
    .force("charge", d3.forceManyBody())
    .force("collide", forceCollide(50))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .on("tick", ticked /*() => console.log(nodes)*/ ); //nodes[0].x



// Declare the x (horizontal position) scale.
const x = d3.scaleUtc()
    .domain([new Date("2023-01-01"), new Date("2024-01-01")])
    .range([marginLeft, width - marginRight]);

// Declare the y (vertical position) scale.
const y = d3.scaleLinear()
    .domain([0, 100])
    .range([height - marginBottom, marginTop]);

// Create the SVG container.
const svg = d3.create("svg")
    .attr("width", width)
    .attr("height", height);

//ajouter des marker-end (of line)
svg
    //.append("defs")
    //.selectAll("marker")
    //.data(types)
    .append("marker")
      .attr("id", "triangle")
      .attr("viewBox", "0 0 10 10")
      .attr("refX", 10) //1
      .attr("refY", 5) //5
      .attr("markerUnits", "strokeWidth")
      .attr("markerWidth", 10)
      .attr("markerHeight", 10)
      .attr("orient", "auto")
    .append("path")
      .attr("fill", "#000000")
      .attr("d", "M 0 0 L 10 5 L 0 10 z");


const node = svg.append("g")
//                .attr("stroke", "#fff")
                .attr("stroke-width", 1.5)
                .selectAll()
                .data(nodes)
                .join("g");

  node
      .append("circle")
      .attr("r", 5)
      .attr("fill", d => color_node(d.labels.join("/")));

  node.append("a")
      .attr("href", d => d.url)
      .append("text") //text
      .attr("x", 8)
      .attr("y", "0.31em")
      .attr("fill", "black")
      // //.attr("color", "black")
      //.attr("stroke", "green")
      //.attr("stroke-width", 3)
      .text(d => d.name);
//    .clone(true).lower()
//      .attr("fill", "none")
//      .attr("stroke", "green")
//      .attr("stroke-width", 3);

//                .join('a')
//                .attr("href", d => d.url)
//                .html(" ... ");

//    .join("circle")
//      .attr("r", 5);
//      .attr("fill", d => color(d.group));

node.append("title")
    .text(d => d.labels.join("/").concat(" : ", d.id))

//node.append("text")
//    .attr("text-anchor", "middle")
//    .attr("dy", ".3em")
//    .text('ici')
//    .append("a")
//    .attr("href", d => d.url)
//    .html("link");

// Add the x-axis.
//svg.append("g")
//    .attr("transform", `translate(0,${height - marginBottom})`)
//    .call(d3.axisBottom(x));

// Add the y-axis.
//svg.append("g")
//    .attr("transform", `translate(${marginLeft},0)`)
//    .call(d3.axisLeft(y));

// add links
 const link = svg.append("g")
      //.attr("stroke", "#999")
      .attr("stroke-opacity", 0.6)
    .selectAll()
    .data(links)
    .join("line")
      .attr("stroke-width", d => Math.sqrt(d.value))
      .attr("stroke", d => color_link(d.type))
      .attr("marker-end", "url(#triangle)");

link  .append("text") //text
//      .attr("x", 8)
//      .attr("y", "0.31em")
      .attr("fill", "black")
      // //.attr("color", "black")
      //.attr("stroke", "green")
      //.attr("stroke-width", 3)
      .text(d => d.type);

//ajouter une legende ?
/*
svg.append("defs").selectAll("marker")
    .data(types)
    .join("marker")
      .attr("id", d => `arrow-${d}`)
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 15)
      .attr("refY", -0.5)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
    .append("path")
      .attr("fill", color_link)
      .attr("d", "M0,-5L10,0L0,5");
*/

//link.append("title")
//    .text(d => d.type)

function ticked() {
    link
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);

    node.attr("transform", d => `translate(${d.x},${d.y})`);
    //node
    //    .attr("cx", d => d.x)
    //    .attr("cy", d => d.y);
}

// Append the SVG element.
container.append(svg.node());
