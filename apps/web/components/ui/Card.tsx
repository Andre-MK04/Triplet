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
        "rounded-none border border-line bg-ink-raised p-5 " +
        (hover ? "transition-colors duration-200 hover:border-mint/40 hover:bg-panel " : "") +
        className
      }
    >
      {children}
    </Tag>
  );
}
