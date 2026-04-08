---
layout: default
title: Downloads
description: Downloadable resources — tools, collections, and binaries.
---

Resources for developers and auditors working with Ekklesia.

{% if site.downloads.size > 0 %} {% for download in site.downloads %}

<div class="download-item">
  <div class="download-info">
    <h4>{{ download.title }}</h4>
    <p>{{ download.description }} — {{ download.version }}{% if download.size %} ({{ download.size }}){% endif %}</p>
  </div>
  <a href="{{ download.file | relative_url }}" class="download-btn">Download</a>
</div>
{% endfor %}
{% else %}

<div class="callout callout-info">
<strong>Coming soon.</strong> Downloadable resources like Postman collections, API schemas, and audit tools will be published here as they become available.
</div>

{% endif %}
