const { useMemo, useState, useEffect } = React;

const navLinks = [
  { label: "Home", href: "#home" },
  { label: "Core", href: "#core" },
  { label: "Products", href: "#products" },
  { label: "How it works", href: "#how-it-works" },
  { label: "Pricing", href: "#pricing" },
  { label: "Contact", href: "#contact" },
];

const whyPoints = [
  {
    title: "One controlled environment",
    text: "Valqeron replaces scattered tools with a single operating layer for AI execution.",
  },
  {
    title: "Structured, not improvised",
    text: "Every system runs through clear oversight, auditability, and operational ownership.",
  },
  {
    title: "Modular growth",
    text: "Add AI capabilities without rebuilding your stack or fragmenting teams.",
  },
  {
    title: "Built for serious adoption",
    text: "Designed for organizations that need outcomes, control, and reliability.",
  },
];

const corePillars = [
  "Central governance and oversight",
  "Unified system logic and controls",
  "Stable foundation for every product",
  "Designed for compliance-aware deployment",
];

const coreConnections = [
  "Products",
  "Documents",
  "Results",
  "Oversight",
  "Support",
  "Expansion",
];

const products = [
  {
    name: "Document Intelligence",
    outcome: "Structured extraction",
    detail: "Turn complex documents into controlled, searchable business data.",
  },
  {
    name: "Customer Support AI",
    outcome: "Reliable resolution",
    detail: "Reduce workload while maintaining oversight and tone consistency.",
  },
  {
    name: "Sales Qualification AI",
    outcome: "Sharper pipelines",
    detail: "Qualify inbound leads with traceable decisions and clear signals.",
  },
  {
    name: "Invoice Processing AI",
    outcome: "Operational speed",
    detail: "Automate invoice workflows with validation, routing, and controls.",
  },
  {
    name: "HR Recruitment AI",
    outcome: "Focused hiring",
    detail: "Screen and summarize candidates with structured governance layers.",
  },
  {
    name: "Business Intelligence",
    outcome: "Executive clarity",
    detail: "Surface insights with consistent data lineage and oversight.",
  },
];

const steps = [
  {
    step: "01",
    title: "Connect your environment",
    text: "Integrate key systems, data sources, and operational context.",
  },
  {
    step: "02",
    title: "Bring in documents and policies",
    text: "Load the materials and guardrails that matter to your business.",
  },
  {
    step: "03",
    title: "Activate controlled AI products",
    text: "Launch modular AI capabilities under Valqeron Core.",
  },
  {
    step: "04",
    title: "Review clear results",
    text: "Monitor outputs with reporting, audit trails, and human oversight.",
  },
];

const valuePoints = [
  "Less fragmentation across teams and tooling",
  "More oversight and accountability for AI use",
  "Scalable AI adoption without operational drift",
  "Clearer internal ownership and governance",
  "Reduced operational chaos through structure",
  "Controlled growth across functions",
];

const pricingPackages = [
  {
    tier: "Starter",
    description: "For small companies starting with AI implementation.",
    fee: "€4,500 setup + €1,250/month",
    note: "Workflows are priced separately.",
    ctaLabel: "Discuss Starter",
    ctaStyle: "secondary",
  },
  {
    tier: "Business",
    description:
      "For companies with €1M+ revenue that want operational automation and measurable ROI.",
    fee: "€8,500 setup + €2,500/month",
    note: "Minimum 3 paid workflows.",
    recommended: true,
    ctaLabel: "Book a demo",
    ctaStyle: "primary",
  },
  {
    tier: "Enterprise",
    description:
      "For larger organizations with scale, compliance, governance, and integration needs.",
    fee: "From €15,000 setup + from €5,000/month",
    note: "Minimum 5 paid workflows.",
    ctaLabel: "Request proposal",
    ctaStyle: "secondary",
  },
];

const workflowPricing = [
  {
    name: "Document Knowledge AI",
    price: "€950–€1,750/month",
    benefit: "Turn document libraries into searchable knowledge.",
  },
  {
    name: "Full Document Audit AI",
    price: "€1,500–€3,000/month",
    benefit: "Audit complex documents with traceable output.",
  },
  {
    name: "Customer Support AI",
    price: "€2,000–€5,000/month",
    benefit: "Deflect tickets with controlled responses.",
  },
  {
    name: "Sales Qualification AI",
    price: "€1,750–€4,500/month",
    benefit: "Prioritize inbound leads with clear scoring.",
  },
  {
    name: "Quote & Contract AI",
    price: "€2,000–€5,000/month",
    benefit: "Speed quotes with governed contract logic.",
  },
  {
    name: "Invoice Processing AI",
    price: "€1,500–€4,000/month",
    benefit: "Reduce AP workload with validation.",
  },
  {
    name: "Marketing Automation AI",
    price: "€1,500–€4,000/month",
    benefit: "Launch campaigns with compliance guardrails.",
  },
  {
    name: "Business Intelligence AI",
    price: "€2,500–€6,000/month",
    benefit: "Surface executive insights with lineage.",
  },
  {
    name: "HR Recruitment AI",
    price: "€1,500–€4,000/month",
    benefit: "Screen candidates with structured summaries.",
  },
  {
    name: "Meeting Assistant AI",
    price: "€750–€2,000/month",
    benefit: "Capture decisions and next steps.",
  },
  {
    name: "Compliance Monitoring AI",
    price: "€3,000–€7,500/month",
    benefit: "Continuous oversight and policy monitoring.",
  },
  {
    name: "Governance & Risk AI",
    price: "€3,500–€8,500/month",
    benefit: "Operational risk signals with accountability.",
  },
  {
    name: "ISO / EU AI Act Layer",
    price: "€5,000–€12,500/month",
    benefit: "Compliance layer for regulated deployment.",
  },
];

const differentiation = [
  {
    title: "Controlled systems",
    text: "Valqeron delivers unified systems instead of disconnected AI tools.",
  },
  {
    title: "Modular evolution",
    text: "Expand without rewriting your stack or losing governance context.",
  },
  {
    title: "Operational clarity",
    text: "Structured environment for real business operations, not experiments.",
  },
];

const coreArchitecture = [
  {
    title: "Governance spine",
    text: "Policy controls, approvals, and oversight live in one central layer.",
  },
  {
    title: "Product orchestration",
    text: "Every AI module inherits shared security, data access, and controls.",
  },
  {
    title: "Operational telemetry",
    text: "Structured monitoring, audit trails, and performance visibility.",
  },
];

const coreOutcomes = [
  {
    title: "Safer rollout",
    text: "Controlled deployment reduces operational risk and decision opacity.",
  },
  {
    title: "Cleaner operations",
    text: "Clear ownership and approvals keep teams aligned and accountable.",
  },
  {
    title: "Scalable expansion",
    text: "Add products without rebuilding the governance layer.",
  },
];

const StatCard = ({ label, value }) => (
  <div className="stat-card" data-reveal>
    <div className="stat-value">{value}</div>
    <div className="stat-label">{label}</div>
  </div>
);

const FeatureCard = ({ title, text }) => (
  <div className="card" data-reveal>
    <h3>{title}</h3>
    <p>{text}</p>
  </div>
);

const ContactForm = () => {
  const [form, setForm] = useState({
    name: "",
    email: "",
    company: "",
    message: "",
  });
  const [status, setStatus] = useState({ state: "idle", message: "" });

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setStatus({ state: "loading", message: "" });

    try {
      const response = await fetch("/api/contact", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (!response.ok) {
        throw new Error("Failed to submit");
      }

      setStatus({
        state: "success",
        message: "Thank you. We will respond shortly.",
      });
      setForm({ name: "", email: "", company: "", message: "" });
    } catch (error) {
      setStatus({
        state: "error",
        message: "Unable to send right now. Please try again shortly.",
      });
    }
  };

  return (
    <form className="contact-form" onSubmit={handleSubmit} data-reveal>
      <div className="form-grid">
        <label>
          Name
          <input
            type="text"
            name="name"
            value={form.name}
            onChange={handleChange}
            required
            placeholder="Full name"
          />
        </label>
        <label>
          Email
          <input
            type="email"
            name="email"
            value={form.email}
            onChange={handleChange}
            required
            placeholder="Work email"
          />
        </label>
        <label>
          Company
          <input
            type="text"
            name="company"
            value={form.company}
            onChange={handleChange}
            placeholder="Company name"
          />
        </label>
        <label className="full">
          Message
          <textarea
            name="message"
            value={form.message}
            onChange={handleChange}
            required
            placeholder="Tell us about your environment"
            rows="4"
          ></textarea>
        </label>
      </div>
      <div className="form-actions">
        <button className="btn primary" type="submit" disabled={status.state === "loading"}>
          {status.state === "loading" ? "Sending..." : "Submit request"}
        </button>
        {status.message && (
          <span className={`form-status ${status.state}`}>{status.message}</span>
        )}
      </div>
    </form>
  );
};

const Navbar = () => (
  <header className="navbar">
    <div className="container nav-inner">
      <div className="brand">
        <span className="brand-mark">
          <img src="/static/valqeron-logo.png" alt="Valqeron logo" />
        </span>
      </div>
      <nav className="nav-links">
        {navLinks.map((link) => (
          <a key={link.label} href={link.href}>
            {link.label}
          </a>
        ))}
      </nav>
    </div>
  </header>
);

const TechBand = () => (
  <div className="container">
    <div className="tech-band" aria-hidden="true">
      <div className="tech-band-inner">
        <div className="tech-node"></div>
        <div className="tech-node"></div>
        <div className="tech-node"></div>
        <div className="tech-node"></div>
        <div className="tech-node"></div>
      </div>
    </div>
  </div>
);

const ImageAtmosphere = ({ className, src }) => (
  <div
    className={`image-atmosphere ${className}`}
    style={{ backgroundImage: `url(${src})` }}
    aria-hidden="true"
  />
);

const CoreCircuit = () => (
  <div className="core-circuit" aria-hidden="true" data-reveal>
    <div className="core-circuit-header">
      <span>Core Circuit Map</span>
      <span className="tag">Live</span>
    </div>
    <div className="core-circuit-grid">
      <div className="circuit-node primary">Control</div>
      <div className="circuit-node">Policy</div>
      <div className="circuit-node">Security</div>
      <div className="circuit-node">Audit</div>
      <div className="circuit-node">Approvals</div>
      <div className="circuit-node">Telemetry</div>
      <div className="circuit-node">Risk</div>
      <div className="circuit-node">Expansion</div>
    </div>
  </div>
);

const ProductVisual = () => (
  <div className="products-visual" data-reveal>
    <div className="products-visual-header">
      <span>Product Stack</span>
    </div>
    <div className="products-visual-body">
      <div className="product-layer">
        <div>
          <p>Valqeron Core</p>
          <span>Control layer</span>
        </div>
      </div>
      <div className="product-layer">
        <div>
          <p>Document Intelligence</p>
          <span>Structured extraction</span>
        </div>
      </div>
      <div className="product-layer">
        <div>
          <p>Customer Support AI</p>
          <span>Reliable resolution</span>
        </div>
      </div>
      <div className="product-layer muted">
        <div>
          <p>Expansion Modules</p>
          <span>Ready to deploy</span>
        </div>
      </div>
    </div>
    <div className="products-visual-footer">
      <span>System readiness</span>
      <strong>Enterprise-ready</strong>
    </div>
  </div>
);

const BackgroundAtmosphere = () => (
  <div className="bg-atmosphere" aria-hidden="true">
    <div className="bg-layer bg-grid"></div>
    <div className="bg-layer bg-nodes"></div>
    <div className="bg-layer bg-glow"></div>
  </div>
);

const SiteBackground = () => (
  <div className="site-background" aria-hidden="true"></div>
);

const HomePage = () => (
  <>
    <section className="section hero hero-light" id="home">
      <div className="hero-atmosphere" aria-hidden="true"></div>
      <div className="container">
        <div className="content-panel hero-panel">
          <div className="hero-grid">
            <div className="hero-content" data-reveal>
              <p className="eyebrow">Controlled AI systems for business</p>
              <h1>
                Controlled AI systems for serious businesses.
                <span className="accent"> One environment. Clear oversight.</span>
              </h1>
              <p className="lead">
                Valqeron builds premium AI systems through a structured environment
                anchored by Valqeron Core. Replace fragmented tools with a single
                control layer that delivers AI products, governance, and business
                clarity.
              </p>
              <div className="cta-group">
                <a className="btn primary" href="/#contact">
                  Discuss your environment
                </a>
                <a className="btn secondary" href="/core">
                  Explore Valqeron Core
                </a>
              </div>
              <div className="hero-stats">
                <StatCard label="Unified Control Layer" value="Valqeron Core" />
                <StatCard label="Modular AI Products" value="6+" />
                <StatCard label="Built for Compliance-Aware Teams" value="Enterprise" />
              </div>
            </div>
            <div className="hero-visual" data-reveal>
              <div className="hero-visual-orbit"></div>
              <div className="visual-panel">
                <div className="visual-header">
                  <span>Valqeron Core</span>
                  <span className="tag">Active</span>
                </div>
                <div className="visual-grid">
                  <div className="visual-card">
                    <p>Oversight</p>
                    <span>Governed</span>
                  </div>
                  <div className="visual-card">
                    <p>Documents</p>
                    <span>Connected</span>
                  </div>
                  <div className="visual-card">
                    <p>Products</p>
                    <span>Modular</span>
                  </div>
                  <div className="visual-card">
                    <p>Results</p>
                    <span>Traceable</span>
                  </div>
                  <div className="visual-card">
                    <p>Support</p>
                    <span>Aligned</span>
                  </div>
                  <div className="visual-card">
                    <p>Expansion</p>
                    <span>Planned</span>
                  </div>
                </div>
                <div className="visual-footer">
                  <span>Environment status</span>
                  <strong>Controlled</strong>
                </div>
              </div>
              <div className="hero-visual-lines"></div>
            </div>
          </div>
        </div>
      </div>
    </section>
    <TechBand />

    <section className="section" id="why">
      <div className="container">
        <div className="content-panel">
          <div className="section-heading" data-reveal>
            <p className="eyebrow">Why Valqeron</p>
            <h2>AI deployment without chaos.</h2>
            <p className="subtext">
              Valqeron delivers a structured operating environment for AI systems—
              designed to replace fragmented automations with control, clarity, and
              measurable business impact.
            </p>
          </div>
          <div className="grid">
            {whyPoints.map((point) => (
              <FeatureCard key={point.title} {...point} />
            ))}
          </div>
        </div>
      </div>
    </section>

    <section className="section core" id="core">
      <div className="container">
        <div className="content-panel">
          <div className="section-heading" data-reveal>
            <p className="eyebrow">Valqeron Core</p>
            <h2>The control layer behind every Valqeron system.</h2>
            <p className="subtext">
              Valqeron Core is the central layer that connects products, documents,
              results, oversight, support, and expansion. It provides the structure
              that makes AI deployment stable, auditable, and scalable.
            </p>
          </div>
          <CoreCircuit />
          <div className="core-grid">
            <div className="core-panel" data-reveal>
              <h3>What it delivers</h3>
              <ul>
                {corePillars.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <div className="core-tag">
                Designed for compliance-aware businesses, with structured governance
                and oversight aligned to expectations in the EU AI Act, ISO 27001,
                and ISO 42001.
              </div>
            </div>
            <div className="core-panel" data-reveal>
              <h3>What it connects</h3>
              <div className="chip-grid">
                {coreConnections.map((item) => (
                  <span key={item} className="chip">
                    {item}
                  </span>
                ))}
              </div>
              <p className="core-note">
                The Core is the foundation for modular AI products—so every new
                capability inherits control, visibility, and governance.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section className="section alt" id="products">
      <div className="container">
        <div className="content-panel">
          <div className="section-heading" data-reveal>
            <p className="eyebrow">Products</p>
            <h2>Modular AI products, deployed under one control layer.</h2>
            <p className="subtext">
              Each product is a module activated through Valqeron Core—ensuring
              oversight, consistency, and scalable expansion.
            </p>
          </div>
          <div className="products-layout">
            <ProductVisual />
            <div className="grid">
              {products.map((product) => (
                <div
                  key={product.name}
                  className="card product parallax-card"
                  data-reveal
                >
                  <div className="product-header">
                    <h3>{product.name}</h3>
                    <span>{product.outcome}</span>
                  </div>
                  <p>{product.detail}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>

    <section className="section" id="how-it-works">
      <div className="container">
        <div className="content-panel">
          <div className="section-heading" data-reveal>
            <p className="eyebrow">How it works</p>
            <h2>Simple, controlled, business-ready.</h2>
            <p className="subtext">
              Valqeron delivers a clear path from integration to outcomes—without
              operational noise.
            </p>
          </div>
          <div className="how-layout">
            <div className="how-visual" data-reveal>
              <div className="how-visual-header">
                <span>Execution Flow</span>
              </div>
              <div className="how-visual-body">
                <div className="how-line"></div>
                <div className="how-node">Connect</div>
                <div className="how-node">Context</div>
                <div className="how-node">Activate</div>
                <div className="how-node">Review</div>
              </div>
            </div>
            <div className="steps">
              {steps.map((item) => (
                <div key={item.step} className="step-card" data-reveal>
                  <div className="step-number">{item.step}</div>
                  <div>
                    <h3>{item.title}</h3>
                    <p>{item.text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>

    <section className="section alt" id="value">
      <div className="container">
        <div className="content-panel">
          <div className="section-heading" data-reveal>
            <p className="eyebrow">Why businesses buy</p>
            <h2>Operational value you can defend.</h2>
            <p className="subtext">
              For organizations adopting AI seriously, Valqeron delivers the
              structure needed to scale without losing control.
            </p>
          </div>
          <div className="value-grid">
            {valuePoints.map((point) => (
              <div key={point} className="value-item" data-reveal>
                <span className="value-dot"></span>
                <p>{point}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>

    <section className="section pricing-section" id="pricing">
      <div className="container">
        <div className="pricing-panel content-panel" data-reveal>
          <div className="pricing-hero">
            <p className="eyebrow">Pricing & positioning</p>
            <h2>
              Valqeron builds AI systems that automate business processes, reduce
              operational costs, and provide control and compliance.
            </h2>
            <p className="subtext">
              Built for governance-first rollouts, measurable ROI, and clear
              accountability across teams.
            </p>
          </div>
          <div className="pricing-packages-header">
            <h3>Pricing packages</h3>
            <p>
              Platform access includes trusted controls, with workflows added
              based on operational scope.
            </p>
          </div>
          <div className="pricing-packages">
            {pricingPackages.map((tier) => (
              <div
                key={tier.tier}
                className={`pricing-package${tier.recommended ? " recommended" : ""}`}
                data-reveal
              >
                <div className="package-header">
                  <h3>{tier.tier}</h3>
                  {tier.recommended && <span className="tag">Recommended</span>}
                </div>
                <p className="package-description">{tier.description}</p>
                <div className="package-price">{tier.fee}</div>
                <p className="package-note">{tier.note}</p>
                <a
                  className={`btn ${tier.ctaStyle}`}
                  href="/#contact-form"
                >
                  {tier.ctaLabel}
                </a>
              </div>
            ))}
          </div>
          <div className="pricing-footnote">
            Workflows are priced separately based on scope and compliance needs.
            <a href="/#workflows">View workflow pricing.</a>
          </div>
        </div>
      </div>
    </section>

    <section className="section" id="workflows">
      <div className="container">
        <div className="content-panel">
          <div className="section-heading" data-reveal>
            <p className="eyebrow">Workflow pricing</p>
            <h2>Modular workflows priced to operational scope.</h2>
            <p className="subtext">
              Each workflow is scoped to the depth of automation, compliance, and
              measurable ROI required by your teams.
            </p>
          </div>
          <div className="workflow-card-grid">
            {workflowPricing.map((workflow) => (
              <div key={workflow.name} className="workflow-card" data-reveal>
                <h3>{workflow.name}</h3>
                <div className="workflow-price">{workflow.price}</div>
                <p>{workflow.benefit}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>

    <section className="section alt" id="trust">
      <div className="container">
        <div className="content-panel">
          <div className="section-heading" data-reveal>
            <p className="eyebrow">Trust & differentiation</p>
            <h2>Built for enterprise operations, not AI experiments.</h2>
            <p className="subtext">
              Valqeron delivers control, structure, and expansion without the
              fragmentation typical of AI vendors.
            </p>
          </div>
          <div className="grid">
            {differentiation.map((item) => (
              <FeatureCard key={item.title} {...item} />
            ))}
          </div>
        </div>
      </div>
    </section>

    <section className="section final" id="contact">
      <div className="container">
        <div className="content-panel">
          <div className="final-panel" data-reveal>
            <div>
              <p className="eyebrow">Start with control</p>
              <h2>Book a private Valqeron demo.</h2>
              <p className="subtext">
                Discuss your environment, map your AI priorities, and design a
                controlled rollout with Valqeron Core.
              </p>
            </div>
            <div className="final-actions">
              <a className="btn primary" href="#contact-form">
                Book a demo
              </a>
              <a className="btn secondary" href="#contact-form">
                Discuss your environment
              </a>
              <a className="btn ghost" href="#contact-form">
                Explore the right setup
              </a>
            </div>
          </div>
          <div className="contact-block" id="contact-form">
            <div className="contact-copy" data-reveal>
              <h3>Contact Valqeron</h3>
              <p>
                Share your requirements. We will respond with a structured proposal
                and next steps.
              </p>
            </div>
            <ContactForm />
          </div>
        </div>
      </div>
    </section>
  </>
);

const CorePage = () => (
  <>
    <section className="section hero hero-light core-hero" id="core">
      <div className="container">
        <div className="content-panel hero-panel">
          <div className="hero-grid">
            <div className="hero-content" data-reveal>
              <p className="eyebrow">Valqeron Core</p>
              <h1>
                The control layer behind every Valqeron AI system.
                <span className="accent"> Built for oversight and scale.</span>
              </h1>
              <p className="lead">
                Valqeron Core centralizes governance, security, and operational
                structure so every AI product runs inside a controlled environment.
                It replaces disconnected tooling with a unified system for business
                adoption.
              </p>
              <div className="cta-group">
                <a className="btn primary" href="/#contact">
                  Discuss your environment
                </a>
                <a className="btn secondary" href="/#products">
                  View products
                </a>
              </div>
            </div>
            <div className="hero-visual" data-reveal>
              <div className="visual-panel">
                <div className="visual-header">
                  <span>Core Architecture</span>
                  <span className="tag">Enterprise</span>
                </div>
                <div className="visual-grid">
                  {coreConnections.map((item) => (
                    <div key={item} className="visual-card">
                      <p>Layer</p>
                      <span>{item}</span>
                    </div>
                  ))}
                </div>
                <div className="visual-footer">
                  <span>Governance status</span>
                  <strong>Ready</strong>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section className="section">
      <div className="container">
        <div className="content-panel">
          <div className="section-heading" data-reveal>
            <p className="eyebrow">Core foundation</p>
            <h2>Structure that makes AI safe to scale.</h2>
            <p className="subtext">
              Valqeron Core is designed for compliance-aware businesses. It supports
              governance and oversight aligned to the EU AI Act, ISO 27001, and ISO
              42001 expectations—without claiming certification.
            </p>
          </div>
          <div className="grid">
            {coreArchitecture.map((item) => (
              <FeatureCard key={item.title} {...item} />
            ))}
          </div>
        </div>
      </div>
    </section>

    <section className="section alt">
      <div className="container">
        <div className="content-panel">
          <div className="section-heading" data-reveal>
            <p className="eyebrow">Business impact</p>
            <h2>Why Core matters for operations.</h2>
          </div>
          <div className="grid">
            {coreOutcomes.map((item) => (
              <FeatureCard key={item.title} {...item} />
            ))}
          </div>
        </div>
      </div>
    </section>

    <section className="section">
      <div className="container">
        <div className="content-panel">
          <div className="section-heading" data-reveal>
            <p className="eyebrow">Deployment model</p>
            <h2>From alignment to execution.</h2>
            <p className="subtext">
              Core deployments are structured around your operational priorities and
              governance requirements.
            </p>
          </div>
          <div className="steps">
            {steps.map((item) => (
              <div key={item.step} className="step-card" data-reveal>
                <div className="step-number">{item.step}</div>
                <div>
                  <h3>{item.title}</h3>
                  <p>{item.text}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>

    <section className="section final" id="contact">
      <div className="container">
        <div className="content-panel">
          <div className="final-panel" data-reveal>
            <div>
              <p className="eyebrow">Valqeron Core</p>
              <h2>Design the right control layer.</h2>
              <p className="subtext">
                Schedule a private walkthrough of Valqeron Core and map the ideal
                modular deployment.
              </p>
            </div>
            <div className="final-actions">
              <a className="btn primary" href="/#contact">
                Book a demo
              </a>
              <a className="btn secondary" href="/#contact">
                Discuss your environment
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  </>
);

const App = () => {
  const year = useMemo(() => new Date().getFullYear(), []);
  const [path, setPath] = useState(window.location.pathname);

  useEffect(() => {
    const handleChange = () => setPath(window.location.pathname);
    window.addEventListener("popstate", handleChange);
    return () => window.removeEventListener("popstate", handleChange);
  }, []);

  useEffect(() => {
    document.documentElement.style.setProperty("--scroll", "0");
  }, []);

  useEffect(() => {
    const elements = document.querySelectorAll("[data-reveal]");
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
          }
        });
      },
      { threshold: 0.2 }
    );
    elements.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, [path]);

  const isCore = path.startsWith("/core");

  return (
    <div className="page">
      <div className="glow"></div>
      <SiteBackground />
      <div className="circuit-flow" aria-hidden="true"></div>
      <Navbar />
      <main>{isCore ? <CorePage /> : <HomePage />}</main>
      <footer className="footer">
        <div className="container footer-inner">
          <div>
            <span className="brand-name">Valqeron</span>
            <p>Controlled AI systems for business.</p>
          </div>
          <div className="footer-meta">
            Copyright {year} Valqeron. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
};

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
