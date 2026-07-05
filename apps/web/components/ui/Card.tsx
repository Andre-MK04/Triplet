type CardProps = {
  className?: string;
  children: React.ReactNode;
  as?: "div" | "section" | "article";
  hover?: boolean;
};

export function Card({ className = "", children, as: Tag = "div", hover = false }: CardProps) {
  return (
    <Tag
      className={
        "glass rounded-card p-5 shadow-deal " +
        (hover ? "transition duration-300 hover:-translate-y-1 hover:shadow-lift hover:border-mint/30 " : "") +
        className
      }
    >
      {children}
    </Tag>
  );
}
