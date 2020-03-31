This is the source for [my name dot net](https://marenbeam.net)

If you're interested in my blogging workflow, you can look in `/blog` to see the things I've strung together to make it go. But by means of a summary:

* Write a blog post with regular markdown and put it in `/blog`
* Name it `this-is-what-the-url-is-gonna-be-so-it-better-be-good.md`
* `./build.sh blog-post.md`
* `build.sh` uses bash and Pandoc and a Python [Pandoc filter](https://pandoc.org/filters.html) to generate `this-is-what-the-url-is-gonna-be-so-it-better-be-good.html`, styled how I want
* Sanity-check by looking at it in Firefox (the build script finishes by opening the post in Firefox)
* If all is well, `./publish.sh`
* The server the site is hosted on will fetch the post at the top of the next hour
